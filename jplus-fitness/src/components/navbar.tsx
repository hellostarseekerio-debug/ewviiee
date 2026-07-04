"use client";

import { useEffect, useState } from "react";
import { AnimatePresence, motion } from "framer-motion";
import { Menu, X } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Logo } from "@/components/logo";
import { navLinks } from "@/lib/data";
import { cn } from "@/lib/utils";

export function Navbar() {
  const [scrolled, setScrolled] = useState(false);
  const [open, setOpen] = useState(false);

  useEffect(() => {
    const onScroll = () => setScrolled(window.scrollY > 24);
    onScroll();
    window.addEventListener("scroll", onScroll, { passive: true });
    return () => window.removeEventListener("scroll", onScroll);
  }, []);

  return (
    <motion.header
      initial={{ y: -80, opacity: 0 }}
      animate={{ y: 0, opacity: 1 }}
      transition={{ duration: 0.8, ease: [0.22, 1, 0.36, 1] }}
      className="fixed inset-x-0 top-0 z-50 flex justify-center px-4 pt-4"
    >
      <nav
        aria-label="Main"
        className={cn(
          "flex w-full max-w-7xl items-center justify-between rounded-2xl px-5 py-3 transition-all duration-500",
          scrolled ? "glass shadow-2xl shadow-black/40" : "bg-transparent border border-transparent"
        )}
      >
        <a href="#home" aria-label="J Plus Fitness — home">
          <Logo />
        </a>

        {/* Desktop links */}
        <ul className="hidden items-center gap-1 xl:flex">
          {navLinks.map((link) => (
            <li key={link.href}>
              <a
                href={link.href}
                className="rounded-full px-3.5 py-2 text-sm text-gray-400 transition-colors duration-200 hover:bg-white/5 hover:text-white"
              >
                {link.label}
              </a>
            </li>
          ))}
        </ul>

        <div className="hidden xl:block">
          <Button size="sm">Book Consultation</Button>
        </div>

        {/* Mobile toggle */}
        <button
          type="button"
          onClick={() => setOpen((v) => !v)}
          aria-expanded={open}
          aria-label={open ? "Close menu" : "Open menu"}
          className="rounded-lg p-2 text-gray-300 transition-colors hover:bg-white/5 hover:text-white xl:hidden"
        >
          {open ? <X className="size-5" /> : <Menu className="size-5" />}
        </button>
      </nav>

      {/* Mobile menu */}
      <AnimatePresence>
        {open && (
          <motion.div
            initial={{ opacity: 0, y: -12 }}
            animate={{ opacity: 1, y: 0 }}
            exit={{ opacity: 0, y: -12 }}
            transition={{ duration: 0.25, ease: "easeOut" }}
            className="absolute inset-x-4 top-[76px] rounded-2xl border border-line-strong bg-[#0d0d0d]/95 p-4 shadow-2xl shadow-black/60 backdrop-blur-xl xl:hidden"
          >
            <ul className="flex flex-col">
              {navLinks.map((link) => (
                <li key={link.href}>
                  <a
                    href={link.href}
                    onClick={() => setOpen(false)}
                    className="block rounded-xl px-4 py-3 text-sm text-gray-300 transition-colors hover:bg-white/5 hover:text-white"
                  >
                    {link.label}
                  </a>
                </li>
              ))}
            </ul>
            <div className="mt-3 border-t border-line pt-4 pb-1 px-1">
              <Button className="w-full">Book Consultation</Button>
            </div>
          </motion.div>
        )}
      </AnimatePresence>
    </motion.header>
  );
}

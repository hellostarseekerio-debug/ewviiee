import { Logo } from "@/components/logo";
import { navLinks, contactInfo } from "@/lib/data";

type IconProps = React.SVGProps<SVGSVGElement>;

function InstagramIcon(props: IconProps) {
  return (
    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" {...props}>
      <rect width="20" height="20" x="2" y="2" rx="5" ry="5" />
      <path d="M16 11.37A4 4 0 1 1 12.63 8 4 4 0 0 1 16 11.37z" />
      <line x1="17.5" x2="17.51" y1="6.5" y2="6.5" />
    </svg>
  );
}

function FacebookIcon(props: IconProps) {
  return (
    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" {...props}>
      <path d="M18 2h-3a5 5 0 0 0-5 5v3H7v4h3v8h4v-8h3l1-4h-4V7a1 1 0 0 1 1-1h3z" />
    </svg>
  );
}

function YoutubeIcon(props: IconProps) {
  return (
    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" {...props}>
      <path d="M2.5 17a24.12 24.12 0 0 1 0-10 2 2 0 0 1 1.4-1.4 49.56 49.56 0 0 1 16.2 0A2 2 0 0 1 21.5 7a24.12 24.12 0 0 1 0 10 2 2 0 0 1-1.4 1.4 49.55 49.55 0 0 1-16.2 0A2 2 0 0 1 2.5 17" />
      <path d="m10 15 5-3-5-3z" />
    </svg>
  );
}

const socials = [
  { icon: InstagramIcon, label: "Instagram" },
  { icon: FacebookIcon, label: "Facebook" },
  { icon: YoutubeIcon, label: "YouTube" },
];

export function Footer() {
  return (
    <footer className="border-t border-line">
      <div className="mx-auto max-w-7xl px-6 py-16">
        <div className="flex flex-col justify-between gap-12 md:flex-row">
          <div className="max-w-sm">
            <Logo />
            <p className="mt-5 text-sm leading-relaxed text-gray-500">
              Hong Kong&apos;s premier private personal-training studio.
              Science-based coaching, measurable results, and a 5.0-star
              standard of service in the heart of Central.
            </p>
            <ul className="mt-6 flex gap-3">
              {socials.map((social) => (
                <li key={social.label}>
                  <a
                    href="#home"
                    aria-label={social.label}
                    className="flex size-10 items-center justify-center rounded-full border border-line text-gray-400 transition-all duration-300 hover:border-line-strong hover:bg-white/5 hover:text-white"
                  >
                    <social.icon className="size-4.5" />
                  </a>
                </li>
              ))}
            </ul>
          </div>

          <nav aria-label="Footer" className="grid grid-cols-2 gap-x-16 gap-y-3 sm:grid-cols-2">
            <p className="col-span-2 text-xs font-semibold tracking-widest text-gray-500 uppercase">
              Explore
            </p>
            {navLinks.map((link) => (
              <a
                key={link.href}
                href={link.href}
                className="text-sm text-gray-400 transition-colors duration-200 hover:text-white"
              >
                {link.label}
              </a>
            ))}
          </nav>

          <div className="max-w-xs">
            <p className="text-xs font-semibold tracking-widest text-gray-500 uppercase">
              Visit
            </p>
            <address className="mt-4 text-sm leading-relaxed text-gray-400 not-italic">
              {contactInfo.addressLines.map((line) => (
                <span key={line} className="block">
                  {line}
                </span>
              ))}
            </address>
            <p className="mt-3 text-sm text-gray-400">{contactInfo.phone}</p>
            <p className="text-sm text-gray-400">{contactInfo.email}</p>
          </div>
        </div>

        <div className="mt-14 flex flex-col items-center justify-between gap-4 border-t border-line pt-8 sm:flex-row">
          <p className="text-xs text-gray-600">
            © {new Date().getFullYear()} {contactInfo.company}. All rights reserved.
          </p>
          <p className="text-xs text-gray-600">
            Design mockup — for presentation purposes only.
          </p>
        </div>
      </div>
    </footer>
  );
}

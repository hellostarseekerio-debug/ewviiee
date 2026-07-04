import { Navbar } from "@/components/navbar";
import { Hero } from "@/components/hero";
import { Trust } from "@/components/trust";
import { About } from "@/components/about";
import { Services } from "@/components/services";
import { Transformations } from "@/components/transformations";
import { Coaches } from "@/components/coaches";
import { Process } from "@/components/process";
import { Testimonials } from "@/components/testimonials";
import { Pricing } from "@/components/pricing";
import { Gallery } from "@/components/gallery";
import { Faq } from "@/components/faq";
import { CtaBanner } from "@/components/cta-banner";
import { Contact } from "@/components/contact";
import { Footer } from "@/components/footer";

export default function Home() {
  return (
    <>
      <Navbar />
      <main>
        <Hero />
        <Trust />
        <About />
        <Services />
        <Transformations />
        <Coaches />
        <Process />
        <Testimonials />
        <Pricing />
        <Gallery />
        <Faq />
        <CtaBanner />
        <Contact />
      </main>
      <Footer />
    </>
  );
}

import {
  Activity,
  BarChart3,
  Dumbbell,
  Flame,
  HeartPulse,
  Salad,
  type LucideIcon,
} from "lucide-react";

/* ---------------------------------- Nav ---------------------------------- */

export const navLinks = [
  { label: "Home", href: "#home" },
  { label: "About", href: "#about" },
  { label: "Services", href: "#services" },
  { label: "Transformations", href: "#transformations" },
  { label: "Trainers", href: "#trainers" },
  { label: "Pricing", href: "#pricing" },
  { label: "Reviews", href: "#reviews" },
  { label: "Contact", href: "#contact" },
] as const;

/* --------------------------------- Stats --------------------------------- */

export interface Stat {
  value: number;
  suffix: string;
  decimals?: number;
  label: string;
}

export const heroStats: Stat[] = [
  { value: 500, suffix: "+", label: "Clients Transformed" },
  { value: 5.0, suffix: "★", decimals: 1, label: "Google Rating" },
  { value: 10, suffix: "+", label: "Years of Experience" },
  { value: 100, suffix: "%", label: "Personalized Programs" },
];

/* -------------------------------- Services ------------------------------- */

export interface Service {
  icon: LucideIcon;
  title: string;
  description: string;
  accent: "electric" | "emerald";
}

export const services: Service[] = [
  {
    icon: Dumbbell,
    title: "Personal Training",
    description:
      "One-on-one coaching engineered around your body, your schedule and your goals — never a template.",
    accent: "electric",
  },
  {
    icon: Flame,
    title: "Weight Loss",
    description:
      "Sustainable fat-loss protocols combining resistance training, conditioning and precise nutrition.",
    accent: "emerald",
  },
  {
    icon: Activity,
    title: "Muscle Gain",
    description:
      "Progressive hypertrophy programming with meticulous technique coaching for lean, lasting muscle.",
    accent: "electric",
  },
  {
    icon: HeartPulse,
    title: "Strength Training",
    description:
      "Build foundational strength with barbell fundamentals, periodized cycles and expert supervision.",
    accent: "emerald",
  },
  {
    icon: BarChart3,
    title: "Body Fat Analysis",
    description:
      "Regular body-composition scans track lean mass and body fat, so every decision is data-driven.",
    accent: "electric",
  },
  {
    icon: Salad,
    title: "Nutrition Coaching",
    description:
      "Practical nutrition guidance built around Hong Kong life — no crash diets, just habits that hold.",
    accent: "emerald",
  },
];

/* ----------------------------- Transformations --------------------------- */

export interface Transformation {
  name: string;
  program: string;
  duration: string;
  before: string;
  after: string;
  metrics: { label: string; value: string }[];
}

export const transformations: Transformation[] = [
  {
    name: "Daniel C.",
    program: "Fat Loss + Strength",
    duration: "16 weeks",
    before:
      "https://images.unsplash.com/photo-1571019614242-c5c5dee9f50b?q=80&w=1200&auto=format&fit=crop",
    after:
      "https://images.unsplash.com/photo-1583454110551-21f2fa2afe61?q=80&w=1200&auto=format&fit=crop",
    metrics: [
      { label: "Body Fat", value: "−9.2%" },
      { label: "Lean Mass", value: "+4.1 kg" },
      { label: "Deadlift", value: "+65 kg" },
    ],
  },
  {
    name: "Rachel W.",
    program: "Body Recomposition",
    duration: "24 weeks",
    before:
      "https://images.unsplash.com/photo-1518611012118-696072aa579a?q=80&w=1200&auto=format&fit=crop",
    after:
      "https://images.unsplash.com/photo-1550345332-09e3ac987658?q=80&w=1200&auto=format&fit=crop",
    metrics: [
      { label: "Body Fat", value: "−7.8%" },
      { label: "Waist", value: "−11 cm" },
      { label: "Squat", value: "+40 kg" },
    ],
  },
  {
    name: "Marcus L.",
    program: "Muscle Gain",
    duration: "20 weeks",
    before:
      "https://images.unsplash.com/photo-1434682881908-b43d0467b798?q=80&w=1200&auto=format&fit=crop",
    after:
      "https://images.unsplash.com/photo-1541534741688-6078c6bfb5c5?q=80&w=1200&auto=format&fit=crop",
    metrics: [
      { label: "Lean Mass", value: "+6.4 kg" },
      { label: "Bench Press", value: "+37 kg" },
      { label: "Body Fat", value: "−3.5%" },
    ],
  },
];

/* --------------------------------- Coaches -------------------------------- */

export interface Coach {
  name: string;
  role: string;
  image: string;
  experience: string;
  certifications: string[];
  philosophy: string;
  expertise: string[];
  featured?: boolean;
}

export const coaches: Coach[] = [
  {
    name: "Park Sung-Kwang",
    role: "Head Coach & Founder",
    image:
      "https://images.unsplash.com/photo-1567013127542-490d757e51fc?q=80&w=1200&auto=format&fit=crop",
    experience: "12+ years coaching elite and everyday athletes",
    certifications: ["NSCA-CSCS", "Precision Nutrition L2", "FMS Level 2"],
    philosophy:
      "Every body tells a story. My job is to read it precisely — then rewrite it with detail-oriented coaching, long-term planning and relentless consistency.",
    expertise: [
      "Body Recomposition",
      "Strength & Conditioning",
      "Posture Correction",
      "Nutrition Periodization",
    ],
    featured: true,
  },
  {
    name: "Emily Chan",
    role: "Senior Performance Coach",
    image:
      "https://images.unsplash.com/photo-1571731956672-f2b94d7dd0cb?q=80&w=1200&auto=format&fit=crop",
    experience: "8 years in athletic performance",
    certifications: ["NASM-CPT", "Pre/Postnatal Specialist"],
    philosophy:
      "Strong is a skill. I coach women and men to move better, lift smarter and build confidence that lasts outside the gym.",
    expertise: ["Functional Strength", "Fat Loss", "Mobility"],
  },
  {
    name: "Jason Ho",
    role: "Strength & Conditioning Coach",
    image:
      "https://images.unsplash.com/photo-1594381898411-846e7d193883?q=80&w=1200&auto=format&fit=crop",
    experience: "7 years with competitive athletes",
    certifications: ["ACE-CPT", "Kettlebell Level 2"],
    philosophy:
      "Numbers don't lie. I build athletes with progressive overload, honest tracking and technique before ego.",
    expertise: ["Powerlifting", "Athletic Performance", "Conditioning"],
  },
];

/* --------------------------------- Process -------------------------------- */

export interface ProcessStep {
  step: string;
  title: string;
  description: string;
}

export const processSteps: ProcessStep[] = [
  {
    step: "01",
    title: "Consultation",
    description:
      "A private conversation about your goals, history, lifestyle and schedule — so we design around you.",
  },
  {
    step: "02",
    title: "Assessment",
    description:
      "Full body-composition scan, movement screening and strength baseline. We measure everything.",
  },
  {
    step: "03",
    title: "Personal Plan",
    description:
      "Your coach builds a fully individualized training and nutrition blueprint with clear milestones.",
  },
  {
    step: "04",
    title: "Training",
    description:
      "Focused one-on-one sessions in a private studio — every rep coached, every detail refined.",
  },
  {
    step: "05",
    title: "Progress Tracking",
    description:
      "Monthly re-assessments of body fat, lean mass and strength keep the plan honest and adaptive.",
  },
  {
    step: "06",
    title: "Transformation",
    description:
      "Visible, measurable, sustainable change — and the habits to keep it for life.",
  },
];

/* ------------------------------ Testimonials ------------------------------ */

export interface Testimonial {
  name: string;
  meta: string;
  avatar: string;
  rating: number;
  quote: string;
  tag: string;
}

export const testimonials: Testimonial[] = [
  {
    name: "Victoria Lee",
    meta: "Evening Group Program · 1 year",
    avatar:
      "https://images.unsplash.com/photo-1544005313-94ddf0286df2?q=80&w=400&auto=format&fit=crop",
    rating: 5,
    quote:
      "Since joining the evening group workout last December, I've experienced amazing changes. My strength, energy and body composition have completely transformed.",
    tag: "Transformation",
  },
  {
    name: "M. Y.",
    meta: "Personal Training · 1 month in",
    avatar:
      "https://images.unsplash.com/photo-1507003211169-0a1dd7228f2d?q=80&w=400&auto=format&fit=crop",
    rating: 5,
    quote:
      "My friend recommended this gym and I very much enjoy Coach Park's PT sessions. He is detail-oriented and helps plan out your long-term goals.",
    tag: "Detail-Oriented Coaching",
  },
  {
    name: "Hye Jung Cho",
    meta: "Strength Program · 1 year",
    avatar:
      "https://images.unsplash.com/photo-1534528741775-53994a69daeb?q=80&w=400&auto=format&fit=crop",
    rating: 5,
    quote:
      "I have been working with Sung for a year and he has always been a great help improving my strength and physical abilities. The facilities are extremely well kept.",
    tag: "Strength Gains",
  },
  {
    name: "Alex T.",
    meta: "Body Recomposition · 6 months",
    avatar:
      "https://images.unsplash.com/photo-1500648767791-00dcc994a43e?q=80&w=400&auto=format&fit=crop",
    rating: 5,
    quote:
      "Dropped 8% body fat while gaining muscle. The regular body-fat analysis kept me accountable — and the free protein shakes after sessions don't hurt either.",
    tag: "Fat Loss",
  },
  {
    name: "Sarah K.",
    meta: "Beginner Program · 4 months",
    avatar:
      "https://images.unsplash.com/photo-1494790108377-be9c29b29330?q=80&w=400&auto=format&fit=crop",
    rating: 5,
    quote:
      "As a complete beginner I was nervous, but the environment is so friendly and professional. Every session is planned around my progress. Best decision I've made.",
    tag: "Friendly Environment",
  },
  {
    name: "Kenneth W.",
    meta: "Muscle Gain · 8 months",
    avatar:
      "https://images.unsplash.com/photo-1472099645785-5658abf4ff4e?q=80&w=400&auto=format&fit=crop",
    rating: 5,
    quote:
      "Serious, science-based muscle-gain programming. My lifts have never progressed this consistently. Coach Park plans months ahead — you can feel the expertise.",
    tag: "Muscle Gain",
  },
];

export const reviewHighlights = [
  "Detail-oriented coaching",
  "Muscle gain",
  "Fat loss",
  "Friendly environment",
  "Long-term progress",
  "Professional trainers",
  "Free protein shakes",
  "Body fat analysis",
];

/* --------------------------------- Pricing -------------------------------- */

export interface Plan {
  name: string;
  tagline: string;
  price: string;
  period: string;
  features: string[];
  cta: string;
  highlighted?: boolean;
}

export const plans: Plan[] = [
  {
    name: "Starter",
    tagline: "Begin your transformation",
    price: "HK$4,800",
    period: "/ month",
    features: [
      "4 personal training sessions",
      "Initial body-composition scan",
      "Personalized training plan",
      "WhatsApp coach support",
      "Post-workout protein shakes",
    ],
    cta: "Get Started",
  },
  {
    name: "Premium",
    tagline: "Our most popular program",
    price: "HK$8,800",
    period: "/ month",
    features: [
      "8 personal training sessions",
      "Monthly body-composition analysis",
      "Full nutrition coaching",
      "Priority scheduling",
      "Quarterly program reviews",
      "Post-workout protein shakes",
    ],
    cta: "Start Premium",
    highlighted: true,
  },
  {
    name: "Elite",
    tagline: "Total transformation, fully managed",
    price: "HK$14,800",
    period: "/ month",
    features: [
      "12 personal training sessions",
      "Weekly body-composition analysis",
      "Custom meal planning",
      "24/7 coach access",
      "Recovery & mobility sessions",
      "Guest passes for a partner",
    ],
    cta: "Go Elite",
  },
];

/* --------------------------------- Gallery -------------------------------- */

export interface GalleryImage {
  src: string;
  alt: string;
  tall?: boolean;
}

export const galleryImages: GalleryImage[] = [
  {
    src: "https://images.unsplash.com/photo-1534438327276-14e5300c3a48?q=80&w=1400&auto=format&fit=crop",
    alt: "Main training floor with premium equipment",
    tall: true,
  },
  {
    src: "https://images.unsplash.com/photo-1540497077202-7c8a3999166f?q=80&w=1400&auto=format&fit=crop",
    alt: "Functional training zone",
  },
  {
    src: "https://images.unsplash.com/photo-1517963879433-6ad2b056d712?q=80&w=1400&auto=format&fit=crop",
    alt: "Strength equipment detail",
  },
  {
    src: "https://images.unsplash.com/photo-1571902943202-507ec2618e8f?q=80&w=1400&auto=format&fit=crop",
    alt: "Private coaching studio",
    tall: true,
  },
  {
    src: "https://images.unsplash.com/photo-1558611848-73f7eb4001a1?q=80&w=1400&auto=format&fit=crop",
    alt: "Cardio and conditioning area",
  },
  {
    src: "https://images.unsplash.com/photo-1605296867304-46d5465a13f1?q=80&w=1400&auto=format&fit=crop",
    alt: "Coached barbell session",
  },
  {
    src: "https://images.unsplash.com/photo-1548690312-e3b507d8c110?q=80&w=1400&auto=format&fit=crop",
    alt: "Kettlebell functional training",
    tall: true,
  },
  {
    src: "https://images.unsplash.com/photo-1574680096145-d05b474e2155?q=80&w=1400&auto=format&fit=crop",
    alt: "One-on-one personal training",
  },
];

/* ----------------------------------- FAQ ---------------------------------- */

export interface Faq {
  question: string;
  answer: string;
}

export const faqs: Faq[] = [
  {
    question: "Can complete beginners join?",
    answer:
      "Absolutely — most of our clients start as beginners. Every program begins with a full assessment, and your coach scales every exercise to your current level. You'll never be thrown into a workout you're not ready for.",
  },
  {
    question: "Do you provide nutrition advice?",
    answer:
      "Yes. Nutrition coaching is built into our Premium and Elite plans, and available as an add-on for Starter. We focus on sustainable habits designed around Hong Kong lifestyles — not crash diets.",
  },
  {
    question: "How long until I see results?",
    answer:
      "Most clients feel a difference in energy and strength within 2–3 weeks. Visible body-composition changes typically show at 6–8 weeks, verified by our regular body-fat analysis — we track everything, so progress is never guesswork.",
  },
  {
    question: "How often should I train?",
    answer:
      "For most goals, 2–3 coached sessions per week is the sweet spot. Your coach will design the exact frequency around your recovery, schedule and target timeline during your consultation.",
  },
  {
    question: "Where are you located?",
    answer:
      "We're on the 6th floor of Abdoolally House, 20 Stanley Street, Central — two minutes from Central MTR station, in the heart of Hong Kong.",
  },
  {
    question: "What should I bring to my first session?",
    answer:
      "Just training clothes and shoes. We provide towels, filtered water and a complimentary post-workout protein shake after every session.",
  },
];

/* --------------------------------- Contact -------------------------------- */

export const contactInfo = {
  company: "J Plus Fitness Co Ltd",
  addressLines: ["6/F Abdoolally House", "20 Stanley Street", "Central, Hong Kong"],
  phone: "+852 5969 8277",
  email: "hello@jplusfitness.hk",
  hours: [
    { days: "Monday – Friday", time: "7:00 am – 10:00 pm" },
    { days: "Saturday", time: "8:00 am – 8:00 pm" },
    { days: "Sunday & Holidays", time: "9:00 am – 6:00 pm" },
  ],
};

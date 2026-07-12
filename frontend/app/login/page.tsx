"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import { Building2, ShieldCheck, Globe } from "lucide-react";
import { toast } from "sonner";
import { useAuth } from "@/lib/auth-context";
import { useLanguage, localeLabels, type Locale } from "@/lib/i18n/context";
import { ApiError } from "@/lib/api/types";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";

type Step = "credentials" | "mfa";

const LOCALES: Locale[] = ["en", "zh-HK", "zh-CN"];

export default function LoginPage() {
  const { login, verifyMfa } = useAuth();
  const { locale, setLocale, t } = useLanguage();
  const router = useRouter();

  const [step, setStep] = useState<Step>("credentials");
  const [username, setUsername] = useState("");
  const [password, setPassword] = useState("");
  const [code, setCode] = useState("");
  const [pendingToken, setPendingToken] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [submitting, setSubmitting] = useState(false);

  async function handleCredentialsSubmit(event: React.FormEvent) {
    event.preventDefault();
    setError(null);
    setSubmitting(true);
    try {
      const result = await login(username, password);
      if (result.mfaRequired && result.pendingToken) {
        setPendingToken(result.pendingToken);
        setStep("mfa");
      } else {
        toast.success("Welcome back");
        router.replace("/dashboard");
      }
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Could not reach the server. Please try again.");
    } finally {
      setSubmitting(false);
    }
  }

  async function handleMfaSubmit(event: React.FormEvent) {
    event.preventDefault();
    if (!pendingToken) return;
    setError(null);
    setSubmitting(true);
    try {
      await verifyMfa(pendingToken, code);
      toast.success("Welcome back");
      router.replace("/dashboard");
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Verification failed. Please try again.");
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <div className="flex min-h-screen items-center justify-center bg-muted/40 p-4">
      <div className="w-full max-w-sm">
        <div className="mb-6 flex flex-col items-center gap-2 text-center">
          <div className="flex h-11 w-11 items-center justify-center rounded-xl bg-primary text-primary-foreground">
            <Building2 className="h-6 w-6" />
          </div>
          <h1 className="text-lg font-semibold">{t("login.title")}</h1>
          <p className="text-sm text-muted-foreground">{t("login.subtitle")}</p>
        </div>

        <Card>
          <CardHeader className="flex flex-row items-start justify-between gap-2">
            <div>
              <CardTitle>{step === "credentials" ? t("login.signInHeading") : t("login.mfaHeading")}</CardTitle>
              <CardDescription>
                {step === "credentials" ? t("login.signInDescription") : t("login.mfaDescription")}
              </CardDescription>
            </div>
            <DropdownMenu>
              <DropdownMenuTrigger asChild>
                <Button variant="ghost" size="icon" aria-label={t("topbar.language")} className="shrink-0">
                  <Globe className="h-4 w-4" />
                </Button>
              </DropdownMenuTrigger>
              <DropdownMenuContent align="end">
                {LOCALES.map((code) => (
                  <DropdownMenuItem key={code} onClick={() => setLocale(code)} className={locale === code ? "font-medium" : undefined}>
                    {localeLabels[code]}
                  </DropdownMenuItem>
                ))}
              </DropdownMenuContent>
            </DropdownMenu>
          </CardHeader>
          <CardContent>
            {step === "credentials" ? (
              <form className="flex flex-col gap-4" onSubmit={handleCredentialsSubmit}>
                <div className="flex flex-col gap-1.5">
                  <Label htmlFor="username">{t("login.username")}</Label>
                  <Input
                    id="username"
                    autoComplete="username"
                    value={username}
                    onChange={(e) => setUsername(e.target.value)}
                    required
                    autoFocus
                  />
                </div>
                <div className="flex flex-col gap-1.5">
                  <Label htmlFor="password">{t("login.password")}</Label>
                  <Input
                    id="password"
                    type="password"
                    autoComplete="current-password"
                    value={password}
                    onChange={(e) => setPassword(e.target.value)}
                    required
                  />
                </div>
                {error && <p className="text-sm text-destructive">{error}</p>}
                <Button type="submit" loading={submitting} className="mt-1">
                  {t("login.signIn")}
                </Button>
              </form>
            ) : (
              <form className="flex flex-col gap-4" onSubmit={handleMfaSubmit}>
                <div className="flex flex-col gap-1.5">
                  <Label htmlFor="code" className="flex items-center gap-1.5">
                    <ShieldCheck className="h-3.5 w-3.5" /> {t("login.authCode")}
                  </Label>
                  <Input
                    id="code"
                    inputMode="numeric"
                    autoComplete="one-time-code"
                    value={code}
                    onChange={(e) => setCode(e.target.value)}
                    required
                    autoFocus
                  />
                </div>
                {error && <p className="text-sm text-destructive">{error}</p>}
                <Button type="submit" loading={submitting}>
                  {t("login.verify")}
                </Button>
                <Button type="button" variant="ghost" size="sm" onClick={() => setStep("credentials")}>
                  {t("login.backToSignIn")}
                </Button>
              </form>
            )}
          </CardContent>
        </Card>
      </div>
    </div>
  );
}

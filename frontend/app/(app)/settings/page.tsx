"use client";

import { useEffect, useState } from "react";
import { toast } from "sonner";
import { useTheme } from "next-themes";
import { Copy, KeyRound, Moon, ShieldCheck, Sun, Monitor } from "lucide-react";
import { authApi, settingsApi } from "@/lib/api/endpoints";
import type { MFASetupResponse, SystemSettings } from "@/lib/api/types";
import { ApiError } from "@/lib/api/types";
import { useAuth, hasRole } from "@/lib/auth-context";
import { useLanguage, localeLabels, type Locale } from "@/lib/i18n/context";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Badge } from "@/components/ui/badge";
import { Separator } from "@/components/ui/separator";

export default function SettingsPage() {
  const { user, refreshUser } = useAuth();

  return (
    <div className="flex flex-col gap-5">
      <div>
        <h1 className="text-xl font-semibold tracking-tight">Settings</h1>
        <p className="text-sm text-muted-foreground">Manage your profile, security, and preferences.</p>
      </div>

      <Tabs defaultValue="profile">
        <TabsList>
          <TabsTrigger value="profile">Profile</TabsTrigger>
          <TabsTrigger value="security">Security</TabsTrigger>
          <TabsTrigger value="preferences">Preferences</TabsTrigger>
          {hasRole(user, "admin") && <TabsTrigger value="organization">Organization &amp; AI</TabsTrigger>}
        </TabsList>

        <TabsContent value="profile">
          <ProfileTab />
        </TabsContent>
        <TabsContent value="security">
          <SecurityTab onMfaChange={refreshUser} />
        </TabsContent>
        <TabsContent value="preferences">
          <PreferencesTab />
        </TabsContent>
        {hasRole(user, "admin") && (
          <TabsContent value="organization">
            <OrganizationTab />
          </TabsContent>
        )}
      </Tabs>
    </div>
  );
}

function ProfileTab() {
  const { user } = useAuth();
  const [currentPassword, setCurrentPassword] = useState("");
  const [newPassword, setNewPassword] = useState("");
  const [submitting, setSubmitting] = useState(false);

  async function handlePasswordChange(e: React.FormEvent) {
    e.preventDefault();
    setSubmitting(true);
    try {
      await authApi.changePassword(currentPassword, newPassword);
      toast.success("Password changed");
      setCurrentPassword("");
      setNewPassword("");
    } catch (err) {
      toast.error(err instanceof ApiError ? err.message : "Failed to change password");
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <div className="grid grid-cols-1 gap-4 lg:grid-cols-2">
      <Card>
        <CardHeader>
          <CardTitle>Your profile</CardTitle>
          <CardDescription>Read-only account details. Ask an administrator to update your name or role.</CardDescription>
        </CardHeader>
        <CardContent className="flex flex-col gap-3">
          <div>
            <p className="text-xs font-medium text-muted-foreground">Full name</p>
            <p className="text-sm">{user?.full_name ?? "—"}</p>
          </div>
          <div>
            <p className="text-xs font-medium text-muted-foreground">Username</p>
            <p className="text-sm">{user?.username}</p>
          </div>
          <div>
            <p className="text-xs font-medium text-muted-foreground">Role</p>
            <Badge variant="secondary" className="mt-1 w-fit capitalize">{user?.role}</Badge>
          </div>
          <div>
            <p className="text-xs font-medium text-muted-foreground">Member since</p>
            <p className="text-sm">{user ? new Date(user.created_at).toLocaleDateString() : "—"}</p>
          </div>
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle>Change password</CardTitle>
          <CardDescription>You&apos;ll need your current password to set a new one.</CardDescription>
        </CardHeader>
        <CardContent>
          <form className="flex flex-col gap-3" onSubmit={handlePasswordChange}>
            <div className="flex flex-col gap-1.5">
              <Label htmlFor="current-password">Current password</Label>
              <Input
                id="current-password"
                type="password"
                value={currentPassword}
                onChange={(e) => setCurrentPassword(e.target.value)}
                required
              />
            </div>
            <div className="flex flex-col gap-1.5">
              <Label htmlFor="new-password">New password</Label>
              <Input
                id="new-password"
                type="password"
                value={newPassword}
                onChange={(e) => setNewPassword(e.target.value)}
                required
              />
              <p className="text-xs text-muted-foreground">12+ characters, upper/lower/digit/special character.</p>
            </div>
            <Button type="submit" loading={submitting} className="mt-1 w-fit">
              Update password
            </Button>
          </form>
        </CardContent>
      </Card>
    </div>
  );
}

function SecurityTab({ onMfaChange }: { onMfaChange: () => Promise<void> }) {
  const { user } = useAuth();
  const [enrollment, setEnrollment] = useState<MFASetupResponse | null>(null);
  const [code, setCode] = useState("");
  const [password, setPassword] = useState("");
  const [busy, setBusy] = useState(false);

  async function handleSetup() {
    setBusy(true);
    try {
      setEnrollment(await authApi.setupMfa());
    } catch (err) {
      toast.error(err instanceof ApiError ? err.message : "Could not start MFA setup");
    } finally {
      setBusy(false);
    }
  }

  async function handleConfirm(e: React.FormEvent) {
    e.preventDefault();
    setBusy(true);
    try {
      await authApi.confirmMfa(code);
      toast.success("Two-factor authentication enabled");
      setEnrollment(null);
      setCode("");
      await onMfaChange();
    } catch (err) {
      toast.error(err instanceof ApiError ? err.message : "Invalid code");
    } finally {
      setBusy(false);
    }
  }

  async function handleDisable(e: React.FormEvent) {
    e.preventDefault();
    setBusy(true);
    try {
      await authApi.disableMfa(password);
      toast.success("Two-factor authentication disabled");
      setPassword("");
      await onMfaChange();
    } catch (err) {
      toast.error(err instanceof ApiError ? err.message : "Failed to disable MFA");
    } finally {
      setBusy(false);
    }
  }

  return (
    <Card>
      <CardHeader>
        <CardTitle className="flex items-center gap-2">
          <ShieldCheck className="h-4 w-4" /> Two-factor authentication
        </CardTitle>
        <CardDescription>
          Protects your account with a time-based code from an authenticator app, in addition to your password.
        </CardDescription>
      </CardHeader>
      <CardContent>
        {user?.mfa_enabled ? (
          <form className="flex flex-col gap-3 sm:max-w-sm" onSubmit={handleDisable}>
            <Badge variant="success" className="w-fit">Enabled</Badge>
            <div className="flex flex-col gap-1.5">
              <Label htmlFor="disable-password">Confirm password to disable</Label>
              <Input id="disable-password" type="password" value={password} onChange={(e) => setPassword(e.target.value)} required />
            </div>
            <Button type="submit" variant="destructive" loading={busy} className="w-fit">
              Disable two-factor authentication
            </Button>
          </form>
        ) : enrollment ? (
          <div className="flex flex-col gap-4 sm:max-w-sm">
            <div>
              <p className="text-sm font-medium">1. Scan or enter this key in your authenticator app</p>
              <div className="mt-2 flex items-center gap-2 rounded-md border border-border bg-muted p-2">
                <code className="flex-1 truncate text-xs">{enrollment.secret}</code>
                <Button
                  type="button"
                  variant="ghost"
                  size="icon"
                  className="h-7 w-7"
                  onClick={() => {
                    navigator.clipboard.writeText(enrollment.secret);
                    toast.success("Copied to clipboard");
                  }}
                >
                  <Copy className="h-3.5 w-3.5" />
                </Button>
              </div>
            </div>
            <div>
              <p className="text-sm font-medium">2. Save your recovery codes</p>
              <p className="text-xs text-muted-foreground">Each can be used once if you lose access to your authenticator.</p>
              <div className="mt-2 grid grid-cols-2 gap-1 rounded-md border border-border bg-muted p-2 font-mono text-xs">
                {enrollment.recovery_codes.map((rc) => (
                  <span key={rc}>{rc}</span>
                ))}
              </div>
            </div>
            <form className="flex flex-col gap-2" onSubmit={handleConfirm}>
              <Label htmlFor="mfa-code">3. Enter the 6-digit code to confirm</Label>
              <Input id="mfa-code" value={code} onChange={(e) => setCode(e.target.value)} required />
              <Button type="submit" loading={busy} className="w-fit">
                Confirm and enable
              </Button>
            </form>
          </div>
        ) : (
          <div className="flex flex-col gap-3">
            <Badge variant="outline" className="w-fit">Not enabled</Badge>
            <Button onClick={handleSetup} loading={busy} className="w-fit">
              <KeyRound className="h-4 w-4" /> Set up two-factor authentication
            </Button>
          </div>
        )}
      </CardContent>
    </Card>
  );
}

const LOCALES: Locale[] = ["en", "zh-HK", "zh-CN"];

function PreferencesTab() {
  const { theme, setTheme } = useTheme();
  const { locale, setLocale, t } = useLanguage();
  const options: Array<{ value: string; label: string; icon: React.ElementType }> = [
    { value: "light", label: "Light", icon: Sun },
    { value: "dark", label: "Dark", icon: Moon },
    { value: "system", label: "System", icon: Monitor },
  ];

  return (
    <div className="flex flex-col gap-4">
      <Card>
        <CardHeader>
          <CardTitle>Appearance</CardTitle>
          <CardDescription>Choose how the platform looks on this device.</CardDescription>
        </CardHeader>
        <CardContent className="flex gap-2">
          {options.map((opt) => (
            <Button
              key={opt.value}
              variant={theme === opt.value ? "default" : "outline"}
              onClick={() => setTheme(opt.value)}
            >
              <opt.icon className="h-4 w-4" /> {opt.label}
            </Button>
          ))}
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle>{t("settings.language")}</CardTitle>
          <CardDescription>{t("settings.languageDescription")}</CardDescription>
        </CardHeader>
        <CardContent className="flex flex-wrap gap-2">
          {LOCALES.map((code) => (
            <Button key={code} variant={locale === code ? "default" : "outline"} onClick={() => setLocale(code)}>
              {localeLabels[code]}
            </Button>
          ))}
        </CardContent>
      </Card>
    </div>
  );
}

function OrganizationTab() {
  const [settings, setSettings] = useState<SystemSettings>({});
  const [loading, setLoading] = useState(true);
  const [savingKey, setSavingKey] = useState<string | null>(null);

  useEffect(() => {
    (async () => {
      try {
        setSettings(await settingsApi.get());
      } catch (err) {
        toast.error(err instanceof ApiError ? err.message : "Failed to load settings");
      } finally {
        setLoading(false);
      }
    })();
  }, []);

  async function updateSetting(key: string, value: string) {
    setSavingKey(key);
    try {
      const updated = await settingsApi.update(key, value);
      setSettings(updated);
      toast.success(`${key} updated`);
    } catch (err) {
      toast.error(err instanceof ApiError ? err.message : "Failed to update setting");
    } finally {
      setSavingKey(null);
    }
  }

  if (loading) return <p className="text-sm text-muted-foreground">Loading...</p>;

  const entries = Object.entries(settings);

  return (
    <Card>
      <CardHeader>
        <CardTitle>Organization &amp; AI settings</CardTitle>
        <CardDescription>
          Runtime settings stored in the database - changes apply immediately, no redeploy needed.
        </CardDescription>
      </CardHeader>
      <CardContent className="flex flex-col gap-3">
        {entries.length === 0 ? (
          <p className="text-sm text-muted-foreground">No settings have been configured yet.</p>
        ) : (
          entries.map(([key, value], i) => (
            <div key={key}>
              {i > 0 && <Separator className="mb-3" />}
              <SettingRow settingKey={key} value={value} onSave={updateSetting} saving={savingKey === key} />
            </div>
          ))
        )}
      </CardContent>
    </Card>
  );
}

function SettingRow({
  settingKey,
  value,
  onSave,
  saving,
}: {
  settingKey: string;
  value: string;
  onSave: (key: string, value: string) => void;
  saving: boolean;
}) {
  const [draft, setDraft] = useState(value);
  return (
    <div className="flex flex-col gap-2 sm:flex-row sm:items-end sm:gap-3">
      <div className="flex-1">
        <Label className="text-xs uppercase tracking-wide text-muted-foreground">{settingKey}</Label>
        <Input value={draft} onChange={(e) => setDraft(e.target.value)} className="mt-1" />
      </div>
      <Button
        size="sm"
        variant="outline"
        disabled={draft === value}
        loading={saving}
        onClick={() => onSave(settingKey, draft)}
      >
        Save
      </Button>
    </div>
  );
}

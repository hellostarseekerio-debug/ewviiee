"use client";

import { useCallback, useEffect, useState } from "react";
import { toast } from "sonner";
import { KeyRound, Pencil, ShieldOff, UserPlus, Users as UsersIcon } from "lucide-react";
import { authApi } from "@/lib/api/endpoints";
import type { UserOut, UserRole } from "@/lib/api/types";
import { ApiError } from "@/lib/api/types";
import { useAuth, hasRole } from "@/lib/auth-context";
import { Card, CardContent } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Badge } from "@/components/ui/badge";
import { Skeleton } from "@/components/ui/skeleton";
import { Avatar, AvatarFallback } from "@/components/ui/avatar";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
  DialogDescription,
  DialogFooter,
} from "@/components/ui/dialog";
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";
import { MoreHorizontal } from "lucide-react";

const ROLES: UserRole[] = ["viewer", "reviewer", "editor", "admin"];

export default function UsersPage() {
  const { user: currentUser } = useAuth();
  const [users, setUsers] = useState<UserOut[]>([]);
  const [loading, setLoading] = useState(true);
  const [createOpen, setCreateOpen] = useState(false);
  const [editTarget, setEditTarget] = useState<UserOut | null>(null);
  const [resetTarget, setResetTarget] = useState<UserOut | null>(null);

  const load = useCallback(async () => {
    setLoading(true);
    try {
      setUsers(await authApi.listUsers());
    } catch (err) {
      toast.error(err instanceof ApiError ? err.message : "Failed to load users");
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    load();
  }, [load]);

  async function handleDeactivate(username: string) {
    if (!confirm(`Deactivate ${username}? They will no longer be able to log in.`)) return;
    try {
      await authApi.deactivateUser(username);
      toast.success(`${username} deactivated`);
      load();
    } catch (err) {
      toast.error(err instanceof ApiError ? err.message : "Failed to deactivate user");
    }
  }

  if (!hasRole(currentUser, "admin")) {
    return (
      <div className="flex flex-col items-center gap-2 py-24 text-center">
        <ShieldOff className="h-10 w-10 text-muted-foreground" />
        <p className="font-medium">You don&apos;t have permission to view this page</p>
        <p className="text-sm text-muted-foreground">User management is restricted to administrators.</p>
      </div>
    );
  }

  return (
    <div className="flex flex-col gap-5">
      <div className="flex flex-col justify-between gap-3 sm:flex-row sm:items-center">
        <div>
          <h1 className="text-xl font-semibold tracking-tight">Users</h1>
          <p className="text-sm text-muted-foreground">Manage accounts, roles, and access for your office.</p>
        </div>
        <Button onClick={() => setCreateOpen(true)}>
          <UserPlus className="h-4 w-4" /> Add user
        </Button>
      </div>

      <Card>
        <CardContent className="p-0">
          {loading ? (
            <div className="space-y-2 p-4">
              {Array.from({ length: 4 }).map((_, i) => (
                <Skeleton key={i} className="h-12" />
              ))}
            </div>
          ) : (
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead>User</TableHead>
                  <TableHead>Role</TableHead>
                  <TableHead>MFA</TableHead>
                  <TableHead>Status</TableHead>
                  <TableHead>Last login</TableHead>
                  <TableHead className="w-10" />
                </TableRow>
              </TableHeader>
              <TableBody>
                {users.map((u) => (
                  <TableRow key={u.id}>
                    <TableCell>
                      <div className="flex items-center gap-2.5">
                        <Avatar className="h-8 w-8">
                          <AvatarFallback>{(u.full_name ?? u.username).slice(0, 2).toUpperCase()}</AvatarFallback>
                        </Avatar>
                        <div>
                          <p className="font-medium">{u.full_name ?? u.username}</p>
                          <p className="text-xs text-muted-foreground">@{u.username}</p>
                        </div>
                      </div>
                    </TableCell>
                    <TableCell>
                      <Badge variant="secondary" className="capitalize">
                        {u.role}
                      </Badge>
                    </TableCell>
                    <TableCell>
                      <Badge variant={u.mfa_enabled ? "success" : "outline"}>{u.mfa_enabled ? "Enabled" : "Off"}</Badge>
                    </TableCell>
                    <TableCell>
                      <Badge variant={u.is_active ? "success" : "destructive"}>{u.is_active ? "Active" : "Inactive"}</Badge>
                    </TableCell>
                    <TableCell className="text-muted-foreground">
                      {u.last_login_at ? new Date(u.last_login_at).toLocaleString() : "Never"}
                    </TableCell>
                    <TableCell>
                      <DropdownMenu>
                        <DropdownMenuTrigger asChild>
                          <Button variant="ghost" size="icon" className="h-8 w-8">
                            <MoreHorizontal className="h-4 w-4" />
                          </Button>
                        </DropdownMenuTrigger>
                        <DropdownMenuContent align="end">
                          <DropdownMenuItem onClick={() => setEditTarget(u)}>
                            <Pencil className="h-4 w-4" /> Edit
                          </DropdownMenuItem>
                          <DropdownMenuItem onClick={() => setResetTarget(u)}>
                            <KeyRound className="h-4 w-4" /> Reset password
                          </DropdownMenuItem>
                          {u.username !== currentUser?.username && (
                            <DropdownMenuItem destructive onClick={() => handleDeactivate(u.username)}>
                              <ShieldOff className="h-4 w-4" /> Deactivate
                            </DropdownMenuItem>
                          )}
                        </DropdownMenuContent>
                      </DropdownMenu>
                    </TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          )}
          {!loading && users.length === 0 && (
            <div className="flex flex-col items-center gap-2 px-6 py-16 text-center">
              <UsersIcon className="h-10 w-10 text-muted-foreground" />
              <p className="text-sm text-muted-foreground">No users yet.</p>
            </div>
          )}
        </CardContent>
      </Card>

      <CreateUserDialog open={createOpen} onOpenChange={setCreateOpen} onCreated={load} />
      {editTarget && (
        <EditUserDialog user={editTarget} onOpenChange={(open) => !open && setEditTarget(null)} onSaved={load} />
      )}
      {resetTarget && (
        <ResetPasswordDialog user={resetTarget} onOpenChange={(open) => !open && setResetTarget(null)} />
      )}
    </div>
  );
}

function CreateUserDialog({
  open,
  onOpenChange,
  onCreated,
}: {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  onCreated: () => void;
}) {
  const [username, setUsername] = useState("");
  const [fullName, setFullName] = useState("");
  const [password, setPassword] = useState("");
  const [role, setRole] = useState<UserRole>("viewer");
  const [submitting, setSubmitting] = useState(false);

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    setSubmitting(true);
    try {
      await authApi.createUser({ username, password, full_name: fullName || undefined, role });
      toast.success(`${username} created`);
      onOpenChange(false);
      setUsername("");
      setFullName("");
      setPassword("");
      setRole("viewer");
      onCreated();
    } catch (err) {
      toast.error(err instanceof ApiError ? err.message : "Failed to create user");
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent>
        <DialogHeader>
          <DialogTitle>Add a new user</DialogTitle>
          <DialogDescription>They&apos;ll be able to sign in with the password you set here.</DialogDescription>
        </DialogHeader>
        <form className="flex flex-col gap-3" onSubmit={handleSubmit}>
          <div className="flex flex-col gap-1.5">
            <Label htmlFor="new-username">Username</Label>
            <Input id="new-username" value={username} onChange={(e) => setUsername(e.target.value)} required />
          </div>
          <div className="flex flex-col gap-1.5">
            <Label htmlFor="new-fullname">Full name</Label>
            <Input id="new-fullname" value={fullName} onChange={(e) => setFullName(e.target.value)} />
          </div>
          <div className="flex flex-col gap-1.5">
            <Label htmlFor="new-password">Temporary password</Label>
            <Input id="new-password" type="password" value={password} onChange={(e) => setPassword(e.target.value)} required />
            <p className="text-xs text-muted-foreground">12+ characters, upper/lower/digit/special character.</p>
          </div>
          <div className="flex flex-col gap-1.5">
            <Label>Role</Label>
            <Select value={role} onValueChange={(v) => setRole(v as UserRole)}>
              <SelectTrigger>
                <SelectValue />
              </SelectTrigger>
              <SelectContent>
                {ROLES.map((r) => (
                  <SelectItem key={r} value={r} className="capitalize">
                    {r}
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
          </div>
          <DialogFooter>
            <Button type="submit" loading={submitting}>
              Create user
            </Button>
          </DialogFooter>
        </form>
      </DialogContent>
    </Dialog>
  );
}

function EditUserDialog({
  user,
  onOpenChange,
  onSaved,
}: {
  user: UserOut;
  onOpenChange: (open: boolean) => void;
  onSaved: () => void;
}) {
  const [fullName, setFullName] = useState(user.full_name ?? "");
  const [role, setRole] = useState<UserRole>(user.role);
  const [submitting, setSubmitting] = useState(false);

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    setSubmitting(true);
    try {
      await authApi.updateUser(user.username, { full_name: fullName, role });
      toast.success(`${user.username} updated`);
      onOpenChange(false);
      onSaved();
    } catch (err) {
      toast.error(err instanceof ApiError ? err.message : "Failed to update user");
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <Dialog open onOpenChange={onOpenChange}>
      <DialogContent>
        <DialogHeader>
          <DialogTitle>Edit {user.username}</DialogTitle>
        </DialogHeader>
        <form className="flex flex-col gap-3" onSubmit={handleSubmit}>
          <div className="flex flex-col gap-1.5">
            <Label htmlFor="edit-fullname">Full name</Label>
            <Input id="edit-fullname" value={fullName} onChange={(e) => setFullName(e.target.value)} />
          </div>
          <div className="flex flex-col gap-1.5">
            <Label>Role</Label>
            <Select value={role} onValueChange={(v) => setRole(v as UserRole)}>
              <SelectTrigger>
                <SelectValue />
              </SelectTrigger>
              <SelectContent>
                {ROLES.map((r) => (
                  <SelectItem key={r} value={r} className="capitalize">
                    {r}
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
          </div>
          <DialogFooter>
            <Button type="submit" loading={submitting}>
              Save changes
            </Button>
          </DialogFooter>
        </form>
      </DialogContent>
    </Dialog>
  );
}

function ResetPasswordDialog({ user, onOpenChange }: { user: UserOut; onOpenChange: (open: boolean) => void }) {
  const [password, setPassword] = useState("");
  const [submitting, setSubmitting] = useState(false);

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    setSubmitting(true);
    try {
      await authApi.resetPassword(user.username, password);
      toast.success(`Password reset for ${user.username}`);
      onOpenChange(false);
    } catch (err) {
      toast.error(err instanceof ApiError ? err.message : "Failed to reset password");
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <Dialog open onOpenChange={onOpenChange}>
      <DialogContent>
        <DialogHeader>
          <DialogTitle>Reset password for {user.username}</DialogTitle>
          <DialogDescription>They should change it again after logging in.</DialogDescription>
        </DialogHeader>
        <form className="flex flex-col gap-3" onSubmit={handleSubmit}>
          <div className="flex flex-col gap-1.5">
            <Label htmlFor="reset-password">New password</Label>
            <Input id="reset-password" type="password" value={password} onChange={(e) => setPassword(e.target.value)} required />
          </div>
          <DialogFooter>
            <Button type="submit" loading={submitting}>
              Reset password
            </Button>
          </DialogFooter>
        </form>
      </DialogContent>
    </Dialog>
  );
}

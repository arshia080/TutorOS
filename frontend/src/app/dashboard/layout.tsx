"use client";

import Link from "next/link";
import { usePathname, useRouter } from "next/navigation";
import { Button } from "@/components/ui/button";
import { useAuth } from "@/lib/use-auth";
import { clearToken } from "@/lib/auth";

const TEACHER_NAV_ITEMS = [
  { href: "/dashboard", label: "Overview" },
  { href: "/dashboard/batches", label: "Batches" },
  { href: "/dashboard/students", label: "Students" },
  { href: "/dashboard/subjects", label: "Subjects" },
  { href: "/dashboard/homework", label: "Homework" },
  { href: "/dashboard/assessments", label: "Assessments" },
  { href: "/dashboard/analytics", label: "Analytics" },
];

const STUDENT_NAV_ITEMS = [
  { href: "/dashboard/homework", label: "Homework" },
  { href: "/dashboard/assessments", label: "Tests" },
];

export default function DashboardLayout({ children }: { children: React.ReactNode }) {
  const { user, loading } = useAuth();
  const pathname = usePathname();
  const router = useRouter();

  if (loading) {
    return <div className="flex min-h-screen items-center justify-center">Loading...</div>;
  }

  if (!user) return null;

  const navItems = user.role === "TEACHER" ? TEACHER_NAV_ITEMS : STUDENT_NAV_ITEMS;

  return (
    <div className="flex min-h-screen">
      <aside className="w-56 shrink-0 bg-sidebar p-4 text-sidebar-foreground">
        <Link href="/" className="mb-6 block px-2 text-lg font-semibold tracking-tight">
          Tutor<span className="text-sidebar-primary">OS</span>
        </Link>
        <nav className="space-y-1">
          {navItems.map((item) => (
            <Link
              key={item.href}
              href={item.href}
              className={`block rounded-md px-2 py-1.5 text-sm transition-colors ${
                pathname === item.href
                  ? "bg-sidebar-primary text-sidebar-primary-foreground font-medium"
                  : "text-sidebar-foreground/80 hover:bg-sidebar-accent hover:text-sidebar-accent-foreground"
              }`}
            >
              {item.label}
            </Link>
          ))}
        </nav>
        <div className="mt-8 border-t border-sidebar-border pt-4">
          <p className="px-2 text-sm font-medium">{user.name}</p>
          <p className="px-2 text-xs text-sidebar-foreground/60">{user.role}</p>
          <Button
            variant="ghost"
            size="sm"
            className="mt-2 w-full justify-start text-sidebar-foreground/80 hover:bg-sidebar-accent hover:text-sidebar-accent-foreground"
            onClick={() => {
              clearToken();
              router.replace("/login");
            }}
          >
            Log out
          </Button>
        </div>
      </aside>
      <main className="flex-1 p-8">{children}</main>
    </div>
  );
}

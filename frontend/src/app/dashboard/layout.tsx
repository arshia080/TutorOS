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
      <aside className="w-56 shrink-0 border-r bg-muted/30 p-4">
        <p className="mb-6 px-2 text-lg font-semibold">TutorOS</p>
        <nav className="space-y-1">
          {navItems.map((item) => (
            <Link
              key={item.href}
              href={item.href}
              className={`block rounded-md px-2 py-1.5 text-sm ${
                pathname === item.href ? "bg-primary text-primary-foreground" : "hover:bg-muted"
              }`}
            >
              {item.label}
            </Link>
          ))}
        </nav>
        <div className="mt-8 border-t pt-4">
          <p className="px-2 text-sm font-medium">{user.name}</p>
          <p className="px-2 text-xs text-muted-foreground">{user.role}</p>
          <Button
            variant="ghost"
            size="sm"
            className="mt-2 w-full justify-start"
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

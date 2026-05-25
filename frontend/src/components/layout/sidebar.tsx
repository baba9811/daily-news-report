"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import {
  LayoutDashboard,
  FileText,
  BarChart3,
  RotateCcw,
  Settings,
  Calendar,
  Bot,
  MessageSquare,
  Brain,
  Boxes,
} from "lucide-react";
import { cn } from "@/lib/utils";

interface NavItem {
  href: string;
  label: string;
  icon: React.ReactNode;
}

const navItems: NavItem[] = [
  {
    href: "/",
    label: "Dashboard",
    icon: <LayoutDashboard size={20} />,
  },
  {
    href: "/reports",
    label: "Reports",
    icon: <FileText size={20} />,
  },
  {
    href: "/performance",
    label: "Performance",
    icon: <BarChart3 size={20} />,
  },
  {
    href: "/retrospective",
    label: "Retrospective",
    icon: <RotateCcw size={20} />,
  },
  {
    href: "/agents",
    label: "Agents",
    icon: <Bot size={20} />,
  },
  {
    href: "/debate",
    label: "Debates",
    icon: <MessageSquare size={20} />,
  },
  {
    href: "/memory",
    label: "Memory",
    icon: <Brain size={20} />,
  },
  {
    href: "/multica",
    label: "Multica",
    icon: <Boxes size={20} />,
  },
  {
    href: "/settings",
    label: "Settings",
    icon: <Settings size={20} />,
  },
];

export default function Sidebar() {
  const pathname = usePathname();

  function isActive(href: string): boolean {
    if (href === "/") return pathname === "/";
    return pathname.startsWith(href);
  }

  return (
    <aside className="fixed left-0 top-0 z-40 flex h-screen w-60 flex-col border-r border-[var(--border-color)] bg-[var(--bg-card)]">
      {/* Logo */}
      <div className="flex items-center gap-3 border-b border-[var(--border-color)] px-5 py-5">
        <Calendar size={28} className="text-blue-400" />
        <div>
          <h1 className="text-base font-bold text-[var(--text-primary)]">
            Daily Scheduler
          </h1>
          <p className="text-xs text-[var(--text-secondary)]">
            AI-Powered Reports
          </p>
        </div>
      </div>

      {/* Navigation */}
      <nav className="flex-1 space-y-1 px-3 py-4">
        {navItems.map((item) => (
          <Link
            key={item.href}
            href={item.href}
            className={cn(
              "flex items-center gap-3 rounded-lg px-3 py-2.5 text-sm font-medium transition-colors",
              isActive(item.href)
                ? "bg-blue-500/20 text-blue-400"
                : "text-[var(--text-secondary)] hover:bg-[var(--bg-hover)] hover:text-[var(--text-primary)]"
            )}
          >
            {item.icon}
            {item.label}
          </Link>
        ))}
      </nav>

      {/* Footer */}
      <div className="border-t border-[var(--border-color)] px-5 py-4">
        <p className="text-xs text-[var(--text-secondary)]">
          Daily Scheduler v0.1.0
        </p>
      </div>
    </aside>
  );
}

"use client";

import { useEffect, useState } from "react";
import { Button } from "@/components/ui/button";
import { useRouter } from "next/navigation";
import {
  ChevronFirst,
  ChevronLast,
  LogOut,
  Users,
  Code,
  FileText,
  TrendingUp,
} from "lucide-react";

const menuItems = [
  { id: 2, label: "Candidates", icon: Users, link: "/candidates" },
  {
    id: 3,
    label: "Programming Questions",
    icon: Code,
    link: "/Programming_Questions",
  },
  { id: 4, label: "Job Description", icon: FileText, link: "/Job_Description" },
  { id: 5, label: "Ranking", icon: TrendingUp, link: "/Ranking" },
];

interface SidebarProps {
  onToggle?: (expanded: boolean) => void;
}

export default function Sidebar({ onToggle }: SidebarProps) {
  const [expanded, setExpanded] = useState(true);
  const [user, setUser] = useState<{ name?: string } | null>(null);
  const router = useRouter();

  useEffect(() => {
    (async () => {
      try {
        const r = await fetch("/api/auth/me", { credentials: "include" });
        setUser(r.ok ? await r.json() : null);
      } catch {
        setUser(null);
      }
    })();
  }, []);

  const handleToggle = () => {
    const newExpanded = !expanded;
    setExpanded(newExpanded);
    onToggle?.(newExpanded);
  };

  return (
    <aside
      className={`fixed left-0 top-0 z-40 h-screen border-r shadow-lg
      bg-gradient-to-b from-[#341ba5] via-[#60adce] to-[#71e6e0] text-white
      ${expanded ? "w-64" : "w-16"} transition-[width] duration-300`}
      style={{
        background:
          "linear-gradient(to bottom, #341ba5 0%, #60adce 50%, #71e6e0 100%)",
        color: "#ffffff",
      }}
    >
      {/* inner can scroll if tall */}
      <nav className="h-full flex flex-col overflow-y-auto bg-transparent">
        <div className="flex h-16 items-center justify-between px-3 bg-black/10">
          <div
            className={`overflow-hidden transition-all ${
              expanded ? "w-28" : "w-0"
            }`}
          >
            <h1 className="text-xl font-bold text-white drop-shadow-sm">
              JHire
            </h1>
          </div>
          <Button
            variant="ghost"
            size="icon"
            className="h-8 w-8 text-white hover:bg-white/20 hover:text-white border-0"
            onClick={handleToggle}
            aria-label="Toggle sidebar"
          >
            {expanded ? (
              <ChevronFirst className="text-white" />
            ) : (
              <ChevronLast className="text-white" />
            )}
          </Button>
        </div>

        <div className="flex-1 px-2 py-4 space-y-1">
          {menuItems.map((item) => (
            <button
              key={item.id}
              onClick={() => router.push(item.link)}
              className={`flex w-full items-center rounded px-2 py-2 text-white hover:bg-white/20 hover:text-white transition-all duration-200
                ${expanded ? "justify-start gap-2" : "justify-center"}`}
            >
              <item.icon className="h-5 w-5 text-white" />
              <span
                className={`text-white font-medium ${
                  expanded ? "block" : "hidden"
                }`}
              >
                {item.label}
              </span>
            </button>
          ))}
        </div>

        <div className="mt-auto border-t border-white/30 px-2 py-3 bg-black/10">
          <div
            className={`flex items-center ${
              expanded ? "justify-between" : "justify-center"
            }`}
          >
            {expanded && (
              <span className="text-sm font-medium truncate text-white drop-shadow-sm">
                {user?.name ?? "DemoUser"}
              </span>
            )}
            <button
              className="inline-flex h-8 w-8 items-center justify-center rounded hover:bg-white/20 text-white hover:text-white transition-colors"
              onClick={async () => {
                try {
                  await fetch("/api/auth/logout", { method: "POST" });
                  router.push("/login");
                } catch {
                  // Handle logout error gracefully
                  router.push("/login");
                }
              }}
              aria-label="Log out"
              title="Log out"
            >
              <LogOut className="h-5 w-5 rotate-180 text-white" />
            </button>
          </div>
        </div>
      </nav>
    </aside>
  );
}


"use client";

import { useEffect, useState } from "react";
import { Button } from "@/components/ui/button";
import { ThemeToggle } from "@/components/theme-toggle";
import { Avatar, AvatarFallback, AvatarImage } from "@/components/ui/avatar";
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuLabel,
  DropdownMenuSeparator,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";
import {
  ChevronFirst,
  ChevronLast,
  LogOut,
  Users,
  Home,
  User,
  Code,
  FileText,
  TrendingUp,
} from "lucide-react";
import { useRouter } from "next/navigation";


const menuItems = [
  // { id: 1, label: "Dashboard", icon: Home, link: "/dashboard" },
  { id: 2, label: "Candidates", icon: Users, link: "/candidates" },
  { id: 3, label: "Programming Questions", icon: Code, link: "/Programming_Questions" },
  { id: 4, label: "Job Description", icon: FileText, link: "/Job_Description" },
  { id: 5, label: "Ranking", icon: TrendingUp, link: "/Ranking" },
];

export default function Sidebar() {
  const [expanded, setExpanded] = useState(true);
  const [user, setUser] = useState<{ name: string; email: string } | null>(null);
  const router = useRouter();

  useEffect(() => {
    async function fetchUser() {
      try {
        const response = await fetch("/api/auth/me", {
          method: "GET",
          credentials: "include",
        });
        if (response.ok) {
          const userData = await response.json();
          setUser(userData);
        } else {
          setUser(null);
        }
      } catch {
        setUser(null);
      }
    }

    fetchUser();
  }, []);

  return (
    <aside
  className={`h-screen ${
    expanded ? "w-64" : "w-16"
  } transition-all duration-300 border-r px-4 bg-gradient-to-b from-[#341ba5] via-[#60adce] to-[#71e6e0] text-white`}
>
  <nav className="h-full flex flex-col text-white">
    <div className="flex items-center justify-between h-16">

      <div
        className={`overflow-hidden transition-all ${expanded ? "w-32" : "w-0"}`}
      >
        <h1 className="text-xl font-bold">JHire</h1>
      </div>
      <Button
        variant="ghost"
        size="icon"
        onClick={() => setExpanded((curr) => !curr)}
        className="h-8 w-8 text-white"
      >
        {expanded ? <ChevronFirst /> : <ChevronLast />}
      </Button>
    </div>

    <div className="flex-1 py-8">
      <div className="space-y-2">
        {menuItems.map((item) => (
          <Button
            key={item.id}
            variant="ghost"
            className={`w-full justify-start text-white ${
              !expanded && "px-2"
            }`}
            onClick={() => router.push(item.link)}
          >
            <item.icon className={`h-5 w-5 ${expanded && "mr-2"}`} />
            <span className={`${!expanded && "hidden"} transition-all`}>
              {item.label}
            </span>
          </Button>
        ))}
      </div>
    </div>

    <div className="border-t border-white pt-4 pb-4">
      <div className="flex items-center justify-between px-2">
        {expanded && (
          <span className="text-sm font-medium">{user?.name || "JHire"}</span>
        )}
        <button
          className={`ml-auto flex items-center justify-center text-lg ${
            expanded ? "text-white" : "text-white-600"
          } hover:text-red-600`}
          onClick={async () => {
            await fetch("/api/auth/logout", { method: "POST" });
            router.push("/login");
          }}
        >
          <LogOut className={`h-5 w-5 rotate-180 ${expanded && "ml-2"}`} />
        </button>
      </div>
    </div>



  </nav>
</aside>

  );
}

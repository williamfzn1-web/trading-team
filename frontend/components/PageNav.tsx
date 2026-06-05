"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";

const PAGES = [
  { href: "/",          label: "儀表板" },
  { href: "/analysis",  label: "回測分析" },
];

export default function PageNav() {
  const pathname = usePathname();

  return (
    <div className="flex items-center gap-1 border-b border-[#1e2636] px-5">
      {PAGES.map(({ href, label }) => {
        const active = pathname === href;
        return (
          <Link
            key={href}
            href={href}
            className={`px-4 py-2.5 text-sm font-medium border-b-2 transition-colors ${
              active
                ? "text-white border-indigo-500"
                : "text-gray-500 border-transparent hover:text-gray-300"
            }`}
          >
            {label}
          </Link>
        );
      })}
    </div>
  );
}

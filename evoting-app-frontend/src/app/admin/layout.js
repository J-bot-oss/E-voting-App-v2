"use client";
import { useAuth } from "@/lib/auth";
import { usePathname, useRouter } from "next/navigation";
import { useEffect } from "react";
import Link from "next/link";

function Icon({ d, size = 18 }) {
  return (
    <svg width={size} height={size} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round">
      {Array.isArray(d) ? d.map((p, i) => <path key={i} d={p} />) : <path d={d} />}
    </svg>
  );
}

const ICONS = {
  dashboard: ["M3 9l9-7 9 7v11a2 2 0 01-2 2H5a2 2 0 01-2-2z", "M9 22V12h6v10"],
  candidates: ["M17 21v-2a4 4 0 00-4-4H5a4 4 0 00-4-4v2", "M23 21v-2a4 4 0 00-3-3.87", "M16 3.13a4 4 0 010 7.75", "M9 7a4 4 0 100 8 4 4 0 000-8z"],
  stations: ["M21 10c0 7-9 13-9 13s-9-6-9-13a9 9 0 0118 0z", "M12 7a3 3 0 100 6 3 3 0 000-6z"],
  positions: ["M16 4h2a2 2 0 012 2v14a2 2 0 01-2 2H6a2 2 0 01-2-2V6a2 2 0 012-2h2", "M15 2H9a1 1 0 00-1 1v2a1 1 0 001 1h6a1 1 0 001-1V3a1 1 0 00-1-1z", "M12 11h4", "M12 16h4", "M8 11h.01", "M8 16h.01"],
  polls: ["M9 11l3 3L22 4", "M21 12v7a2 2 0 01-2 2H5a2 2 0 01-2-2V5a2 2 0 012-2h11"],
  voters: ["M17 21v-2a4 4 0 00-4-4H5a4 4 0 00-4-4v2", "M9 7a4 4 0 100 8 4 4 0 000-8z"],
  admins: ["M12 15a7 7 0 100-14 7 7 0 000 14z", "M8.21 13.89L7 23l5-3 5 3-1.21-9.12"],
  results: ["M18 20V10", "M12 20V4", "M6 20v-6"],
  statistics: ["M21.21 15.89A10 10 0 118 2.83", "M22 12A10 10 0 0012 2v10z"],
  audit: ["M14 2H6a2 2 0 00-2 2v16a2 2 0 002 2h12a2 2 0 002-2V8z", "M14 2v6h6", "M16 13H8", "M16 17H8", "M10 9H8"],
};

const NAV = [
  { section: "Election Management", items: [
    { label: "Dashboard", href: "/admin", icon: "dashboard" },
    { label: "Candidates", href: "/admin/candidates", icon: "candidates" },
    { label: "Stations", href: "/admin/stations", icon: "stations" },
    { label: "Positions", href: "/admin/positions", icon: "positions" },
    { label: "Polls", href: "/admin/polls", icon: "polls" },
  ]},
  { section: "People", items: [
    { label: "Voters", href: "/admin/voters", icon: "voters" },
    { label: "Admins", href: "/admin/admins", icon: "admins" },
  ]},
  { section: "Reports", items: [
    { label: "Results", href: "/admin/results", icon: "results" },
    { label: "Statistics", href: "/admin/statistics", icon: "statistics" },
    { label: "Audit Log", href: "/admin/audit", icon: "audit" },
  ]},
];

export default function AdminLayout({ children }) {
  const { user, loading, logout } = useAuth();
  const pathname = usePathname();
  const router = useRouter();

  useEffect(() => {
    if (!loading && (!user || user.role === "voter")) router.push("/login");
  }, [user, loading, router]);

  if (loading || !user) return null;

  return (
    <>
      <header className="topbar">
        <div className="topbar-brand">
          <img src="/logo.png" alt="Logo" />
          <span>Electoral Commission</span>
        </div>
        <div className="topbar-right">
          <div className="topbar-user">
            <strong>{user.full_name}</strong>
            <br />
            <span style={{ fontSize: "0.75rem", color: "var(--gold-light)" }}>{user.role?.replace("_", " ").toUpperCase()}</span>
          </div>
          <button className="btn btn-outline btn-sm" style={{ color: "var(--gray-400)", borderColor: "var(--gray-600)" }} onClick={logout}>
            Logout
          </button>
        </div>
      </header>
      <aside className="sidebar">
        {NAV.map((group) => (
          <div className="sidebar-section" key={group.section}>
            <div className="sidebar-section-title">{group.section}</div>
            {group.items.map((item) => (
              <Link key={item.href} href={item.href} className={`sidebar-link ${pathname === item.href ? "active" : ""}`}>
                <span style={{ width: 20, display: "flex", alignItems: "center", justifyContent: "center", flexShrink: 0 }}>
                  <Icon d={ICONS[item.icon]} />
                </span>
                {item.label}
              </Link>
            ))}
          </div>
        ))}
      </aside>
      <main className="main-content">{children}</main>
    </>
  );
}
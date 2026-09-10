"use client";

import React, { useState, useEffect } from "react";
import Link from "next/link";
import { usePathname } from "next/navigation";
import { EchoLogo } from "./EchoLogo";
import { Volume2, VolumeX, Menu, X } from "lucide-react";

interface NavbarProps {
  soundEnabled?: boolean;
  onToggleSound?: () => void;
}

export const Navbar: React.FC<NavbarProps> = ({
  soundEnabled = true,
  onToggleSound,
}) => {
  const [scrolled, setScrolled] = useState(false);
  const [mobileMenuOpen, setMobileMenuOpen] = useState(false);
  const pathname = usePathname();

  useEffect(() => {
    const handleScroll = () => {
      setScrolled(window.scrollY > 20);
    };
    window.addEventListener("scroll", handleScroll);
    return () => window.removeEventListener("scroll", handleScroll);
  }, []);

  const navLinks = [
    { label: "OVERVIEW", href: "/" },
    { label: "DETECTION", href: "/detection" },
    { label: "VERIFICATION", href: "/verification" },
    { label: "ABOUT", href: "/about" },
  ];

  return (
    <header
      className={`fixed top-0 left-0 right-0 z-40 transition-all duration-300 ${
        scrolled
          ? "bg-[#090b11]/85 backdrop-blur-md border-b border-[rgba(255,255,255,0.08)] py-3"
          : "bg-transparent py-5"
      }`}
    >
      <div className="max-w-7xl mx-auto px-5 sm:px-8 flex items-center justify-between">
        {/* Left: Brand / Logo */}
        <Link href="/" className="flex items-center gap-3 group">
          <EchoLogo size={32} />
          <div className="flex flex-col">
            <span className="text-sm font-mono font-bold tracking-[0.2em] text-[#f4f5f7] group-hover:text-white transition-colors">
              ECHOSENTINEL
            </span>
            <span className="text-[9px] font-mono tracking-[0.25em] text-[#9ba2b1] uppercase">
              Voice Security
            </span>
          </div>
        </Link>

        {/* Center: Desktop Navigation Links */}
        <nav className="hidden md:flex items-center gap-8 text-xs font-mono tracking-widest text-[#9ba2b1]">
          {navLinks.map((link) => {
            const isActive = pathname === link.href;
            return (
              <Link
                key={link.href}
                href={link.href}
                className={`transition-colors py-1 relative ${
                  isActive ? "text-[#f4f5f7] font-semibold" : "hover:text-[#f4f5f7]"
                }`}
              >
                {link.label}
                {isActive && (
                  <span className="absolute bottom-0 left-0 right-0 h-[1.5px] bg-[#66b7ff]" />
                )}
              </Link>
            );
          })}
        </nav>

        {/* Right: Sound Toggle & Mobile Hamburger */}
        <div className="flex items-center gap-3">
          {onToggleSound && (
            <button
              type="button"
              onClick={onToggleSound}
              aria-label={soundEnabled ? "Mute audio" : "Enable audio"}
              className="p-2 rounded-full border border-[rgba(255,255,255,0.12)] bg-[#111520] hover:bg-[#181c27] text-[#9ba2b1] hover:text-[#f4f5f7] transition-colors flex items-center gap-1.5 text-xs font-mono"
            >
              {soundEnabled ? (
                <>
                  <Volume2 size={14} className="text-[#66b7ff]" />
                  <span className="hidden sm:inline text-[10px]">SOUND ON</span>
                </>
              ) : (
                <>
                  <VolumeX size={14} />
                  <span className="hidden sm:inline text-[10px]">SOUND OFF</span>
                </>
              )}
            </button>
          )}

          {/* Mobile Menu Button */}
          <button
            type="button"
            onClick={() => setMobileMenuOpen(!mobileMenuOpen)}
            aria-label="Toggle mobile menu"
            className="md:hidden p-2 rounded-lg border border-[rgba(255,255,255,0.12)] bg-[#111520] text-[#9ba2b1] hover:text-[#f4f5f7]"
          >
            {mobileMenuOpen ? <X size={18} /> : <Menu size={18} />}
          </button>
        </div>
      </div>

      {/* Mobile Drawer */}
      {mobileMenuOpen && (
        <div className="md:hidden bg-[#090b11] border-b border-[rgba(255,255,255,0.12)] px-6 py-5 space-y-4">
          {navLinks.map((link) => (
            <Link
              key={link.href}
              href={link.href}
              onClick={() => setMobileMenuOpen(false)}
              className={`block text-xs font-mono tracking-widest ${
                pathname === link.href ? "text-[#66b7ff] font-semibold" : "text-[#9ba2b1]"
              }`}
            >
              {link.label}
            </Link>
          ))}
        </div>
      )}
    </header>
  );
};

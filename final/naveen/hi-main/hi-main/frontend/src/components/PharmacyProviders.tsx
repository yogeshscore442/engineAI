/**
 * PharmacyProviders.tsx
 *
 * Multi-provider pharmacy panel — like Amazon/Flipkart/Meesho for medicines.
 * Shows 5 trusted Indian pharmacies for every medicine name.
 * Each provider generates a live search URL so links always resolve.
 * Never constructs deep-linked product URLs that break (like /prescriptions/pan-40mg-...).
 */
import React, { useState } from 'react';

interface Provider {
  id: string;
  name: string;
  tagline: string;
  logo: string;       // emoji placeholder; can swap for <img>
  color: string;      // Tailwind bg class for badge
  textColor: string;
  borderColor: string;
  buildUrl: (q: string) => string;
  badge?: string;     // optional trust/feature badge
}

const PROVIDERS: Provider[] = [
  {
    id: '1mg',
    name: 'Tata 1mg',
    tagline: 'Price guaranteed · Authentic',
    logo: '💊',
    color: 'bg-red-50',
    textColor: 'text-red-700',
    borderColor: 'border-red-200',
    // Always use the search page — never a direct product URL that may 404
    buildUrl: (q) =>
      `https://www.1mg.com/search/all?name=${encodeURIComponent(q)}`,
    badge: '⭐ Most Trusted',
  },
  {
    id: 'pharmeasy',
    name: 'PharmEasy',
    tagline: 'Free delivery · Cashback',
    logo: '🏥',
    color: 'bg-purple-50',
    textColor: 'text-purple-700',
    borderColor: 'border-purple-200',
    buildUrl: (q) =>
      `https://pharmeasy.in/search/all?name=${encodeURIComponent(q)}`,
    badge: '🏷️ Best Price',
  },
  {
    id: 'netmeds',
    name: 'Netmeds',
    tagline: 'Reliance · Nationwide delivery',
    logo: '🟢',
    color: 'bg-teal-50',
    textColor: 'text-teal-700',
    borderColor: 'border-teal-200',
    // Use Netmeds search — the /prescriptions/ deep-link 404s
    buildUrl: (q) =>
      `https://www.netmeds.com/catalogsearch/result?q=${encodeURIComponent(q)}`,
  },
  {
    id: 'apollo',
    name: 'Apollo Pharmacy',
    tagline: 'India\'s #1 pharmacy chain',
    logo: '🔵',
    color: 'bg-blue-50',
    textColor: 'text-blue-700',
    borderColor: 'border-blue-200',
    buildUrl: (q) =>
      `https://www.apollopharmacy.in/search-medicines/${encodeURIComponent(q)}`,
    badge: '🏆 Chain Certified',
  },
  {
    id: 'medplus',
    name: 'MedPlus',
    tagline: 'Store pickup · Online order',
    logo: '🟠',
    color: 'bg-orange-50',
    textColor: 'text-orange-700',
    borderColor: 'border-orange-200',
    buildUrl: (q) =>
      `https://www.medplusmart.com/searchMedicines#/medicines?q=${encodeURIComponent(q)}`,
  },
];

interface PharmacyProvidersProps {
  medicineName: string;
  brandName?: string | null;
  genericName?: string | null;
  isPrescriptionOnly?: boolean;
}

export const PharmacyProviders: React.FC<PharmacyProvidersProps> = ({
  medicineName,
  brandName,
  genericName,
  isPrescriptionOnly = false,
}) => {
  const [expanded, setExpanded] = useState(false);

  // Best search query: prefer brand > medicine name, add generic as fallback label
  const searchQuery = brandName || medicineName;

  return (
    <div className="pt-2 border-t border-border-light/60 space-y-2">
      {/* Header row */}
      <div className="flex items-center justify-between text-xs">
        <span className="font-semibold text-text-primary flex items-center gap-1.5">
          <span>🛒</span>
          <span>
            Buy from Trusted Pharmacy&nbsp;
            <span className="text-text-muted font-normal">— {PROVIDERS.length} providers</span>
          </span>
        </span>
        <button
          onClick={() => setExpanded(!expanded)}
          className="text-[11px] text-primary-600 hover:text-primary-700 font-medium underline cursor-pointer"
        >
          {expanded ? 'Hide ▲' : 'Show pharmacies ▼'}
        </button>
      </div>

      {expanded && (
        <div className="space-y-2 animate-in fade-in duration-200">
          {/* Prescription warning */}
          {isPrescriptionOnly && (
            <div className="flex gap-2 p-2.5 bg-amber-50 rounded-lg border border-amber-200 text-[11px] text-amber-800">
              <span>⚠️</span>
              <span>
                <strong>Prescription Required (Rx only):</strong> Upload your doctor's prescription
                on the pharmacy site before checkout. Online dispensing without prescription is illegal.
              </span>
            </div>
          )}

          {/* Provider grid */}
          <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-2">
            {PROVIDERS.map((p) => (
              <a
                key={p.id}
                href={p.buildUrl(searchQuery)}
                target="_blank"
                rel="noopener noreferrer"
                className={`
                  group flex items-center gap-3 p-3 rounded-xl border
                  ${p.color} ${p.borderColor}
                  hover:shadow-md hover:scale-[1.02] transition-all duration-150
                  cursor-pointer no-underline
                `}
              >
                {/* Logo */}
                <span className="text-2xl shrink-0">{p.logo}</span>

                {/* Text */}
                <div className="min-w-0 flex-1">
                  <div className={`font-bold text-sm ${p.textColor} flex items-center gap-1.5`}>
                    {p.name}
                    {p.badge && (
                      <span className="text-[9px] font-semibold bg-white/70 px-1.5 py-0.5 rounded-full border border-current/20">
                        {p.badge}
                      </span>
                    )}
                  </div>
                  <div className="text-[10px] text-text-muted mt-0.5 truncate">{p.tagline}</div>
                </div>

                {/* Arrow */}
                <span className={`text-xs ${p.textColor} opacity-60 group-hover:opacity-100 group-hover:translate-x-0.5 transition-transform`}>
                  →
                </span>
              </a>
            ))}
          </div>

          {/* Generic search hint */}
          {genericName && genericName !== searchQuery && (
            <div className="pt-1 text-[10px] text-text-muted">
              💡 Can't find by brand name?{' '}
              <span className="font-medium text-text-secondary">
                Search for generic: <strong>{genericName}</strong>
              </span>{' '}
              — usually cheaper and equally effective.
            </div>
          )}

          {/* Disclaimer */}
          <p className="text-[10px] text-text-muted text-center pt-1 border-t border-border-light/40">
            🔒 All links open official pharmacy websites over HTTPS. Healthcare Co-Pilot has no
            commercial affiliation, receives no commission, and does not endorse any specific
            pharmacy. Always verify medicine details before purchase.
          </p>
        </div>
      )}
    </div>
  );
};

export default PharmacyProviders;

import React, { useState, useEffect } from 'react';
import type { ProductMatchResult, ProductRecord } from '../types';
import api from '../api';
import { PharmacyProviders } from './PharmacyProviders';

interface ProductDetailsModalProps {
  isOpen: boolean;
  onClose: () => void;
  medicineName: string;
  generic?: string | null;
  strength?: string | null;
  dosageForm?: string | null;
  ocrConfidence?: number;
  userConfirmed?: boolean;
  prescriptionInstructions?: string | null;
  scheduleParsed?: string[] | null;
  foodInstruction?: string | null;
  durationDays?: number | null;
}

export const ProductDetailsModal: React.FC<ProductDetailsModalProps> = ({
  isOpen,
  onClose,
  medicineName,
  generic,
  strength,
  dosageForm,
  ocrConfidence = 1.0,
  userConfirmed = false,
  prescriptionInstructions,
  scheduleParsed,
  foodInstruction,
  durationDays,
}) => {
  const [loading, setLoading] = useState(false);
  const [result, setResult] = useState<ProductMatchResult | null>(null);
  const [selectedProduct, setSelectedProduct] = useState<ProductRecord | null>(null);
  const [showImage, setShowImage] = useState(true);
  const [imageFailed, setImageFailed] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!isOpen || !medicineName) {
      setResult(null);
      setSelectedProduct(null);
      setShowImage(true);
      setImageFailed(false);
      setError(null);
      return;
    }

    let isMounted = true;
    setLoading(true);
    setImageFailed(false);
    setError(null);

    api
      .matchProduct({
        name: medicineName,
        generic: generic || undefined,
        strength: strength || undefined,
        dosage_form: dosageForm || undefined,
        ocr_confidence: ocrConfidence,
        user_confirmed: userConfirmed,
      })
      .then((data) => {
        if (!isMounted) return;
        setResult(data);
        if (data.product) {
          setSelectedProduct(data.product);
        } else if (data.candidate_products.length > 0) {
          setSelectedProduct(data.candidate_products[0]);
        }
      })
      .catch((err) => {
        if (!isMounted) return;
        setError(err?.message || 'Could not fetch catalog details.');
      })
      .finally(() => {
        if (isMounted) setLoading(false);
      });

    return () => {
      isMounted = false;
    };
  }, [isOpen, medicineName, generic, strength, dosageForm, ocrConfidence, userConfirmed]);

  if (!isOpen) return null;

  return (
    <div className="fixed inset-0 z-50 overflow-y-auto bg-slate-900/60 backdrop-blur-xs flex items-center justify-center p-4">
      <div className="relative w-full max-w-xl bg-white rounded-xl shadow-2xl border border-border-light overflow-hidden animate-in fade-in zoom-in-95 duration-200">
        {/* Modal Header */}
        <div className="px-5 py-4 bg-surface-50 border-b border-border-light flex items-center justify-between">
          <div className="flex items-center gap-2">
            <span className="text-xl">💊</span>
            <div>
              <h3 className="font-bold text-text-primary text-base">Verified Medical Catalog Lookup</h3>
              <p className="text-xs text-text-muted">
                Source-aware NLEM reference information & verified pharmaceutical packshots
              </p>
            </div>
          </div>
          <button
            onClick={onClose}
            className="text-text-muted hover:text-text-primary p-1.5 rounded-lg hover:bg-surface-200 transition-colors cursor-pointer"
            aria-label="Close product details"
          >
            ✕
          </button>
        </div>

        {/* Modal Body */}
        <div className="p-5 space-y-4 max-h-[75vh] overflow-y-auto">
          {/* Doctor's Extracted Prescription Directions (Visually Distinct from Catalog) */}
          {(prescriptionInstructions || (scheduleParsed && scheduleParsed.length > 0) || foodInstruction || durationDays) && (
            <div className="p-3.5 bg-blue-50/90 rounded-xl border border-blue-200 space-y-2">
              <div className="flex items-center justify-between">
                <span className="text-xs font-bold text-blue-900 flex items-center gap-1.5">
                  <span>📝</span> Doctor's Prescribed Directions / மருத்துவர் பரிந்துரை
                </span>
                <span className="text-[10px] bg-blue-100 text-blue-800 font-semibold px-2 py-0.5 rounded-full border border-blue-300">
                  Prescribed Order
                </span>
              </div>
              <div className="flex flex-wrap items-center gap-2 pt-1 text-xs text-blue-950 font-medium">
                {prescriptionInstructions && (
                  <div className="bg-white px-2.5 py-1 rounded-md border border-blue-200">
                    <span className="text-text-muted text-[10px] block">Order / Schedule:</span>
                    <strong>{prescriptionInstructions}</strong>
                  </div>
                )}
                {scheduleParsed && scheduleParsed.length > 0 && (
                  <div className="bg-white px-2.5 py-1 rounded-md border border-blue-200">
                    <span className="text-text-muted text-[10px] block">Daily Slots:</span>
                    <div className="flex gap-1 mt-0.5">
                      {scheduleParsed.map((s) => (
                        <span key={s} className="px-1.5 py-0.5 bg-blue-100 text-blue-800 rounded text-[10px] font-bold capitalize">
                          {s}
                        </span>
                      ))}
                    </div>
                  </div>
                )}
                {foodInstruction && (
                  <div className="bg-white px-2.5 py-1 rounded-md border border-blue-200">
                    <span className="text-text-muted text-[10px] block">Food Timing:</span>
                    <strong className="capitalize">{foodInstruction.replace('_', ' ')}</strong>
                  </div>
                )}
                {durationDays ? (
                  <div className="bg-white px-2.5 py-1 rounded-md border border-blue-200">
                    <span className="text-text-muted text-[10px] block">Duration:</span>
                    <strong>{durationDays} days</strong>
                  </div>
                ) : null}
              </div>
              <p className="text-[10px] text-blue-700 italic pt-0.5">
                Note: Take strictly according to your physician's prescription order. Reference catalog guidance is shown below.
              </p>
            </div>
          )}

          {/* Query Summary Banner */}
          <div className="p-3 bg-surface-100/70 rounded-lg text-xs space-y-1 border border-border-light">
            <div className="flex justify-between text-text-secondary">
              <span>Extracted Name: <strong className="text-text-primary">{medicineName}</strong></span>
              {strength && <span>Strength: <strong className="text-text-primary">{strength}</strong></span>}
            </div>
            {generic && (
              <div className="text-text-muted">
                Generic Active Salt: <span className="font-medium text-text-secondary">{generic}</span>
              </div>
            )}
          </div>

          {loading && (
            <div className="py-10 text-center space-y-2">
              <div className="w-8 h-8 border-3 border-primary-500 border-t-transparent rounded-full animate-spin mx-auto"></div>
              <p className="text-xs text-text-muted">Comparing against CDSCO & NLEM verified product catalog...</p>
            </div>
          )}

          {error && (
            <div className="p-4 bg-red-50 text-red-800 rounded-lg text-xs border border-red-200">
              <strong>Lookup Error:</strong> {error}
            </div>
          )}

          {!loading && result && (
            <div className="space-y-4">
              {/* Match State Banner */}
              {result.match_state === 'EXACT_MATCH_VERIFIED' && (
                <div className="p-3 bg-emerald-50 border border-emerald-200 rounded-lg flex items-center gap-2 text-xs text-emerald-800">
                  <span className="text-base">✅</span>
                  <div>
                    <strong>Exact Verified Product Match:</strong> All identifiers (brand/generic, strength, formulation) verified against official catalog.
                  </div>
                </div>
              )}

              {result.match_state === 'MULTIPLE_MATCHES' && (
                <div className="p-3 bg-amber-50 border border-amber-200 rounded-lg text-xs text-amber-800 space-y-1">
                  <div className="flex items-center gap-1.5 font-bold">
                    <span>ℹ️</span> Generic Prescription — Multiple Catalog Options Available
                  </div>
                  <p className="text-[11px] text-amber-700">
                    The uploaded document states a generic ingredient. Select an authorized branded formulation below to view packaging images and 1mg links:
                  </p>
                  {result.candidate_products.length > 1 && (
                    <div className="flex flex-wrap gap-1.5 pt-1">
                      {result.candidate_products.map((cand) => (
                        <button
                          key={cand.product_id}
                          onClick={() => {
                            setSelectedProduct(cand);
                            setShowImage(true);
                            setImageFailed(false);
                          }}
                          className={`px-2 py-1 rounded text-[11px] font-medium border transition-colors cursor-pointer ${
                            selectedProduct?.product_id === cand.product_id
                              ? 'bg-amber-600 text-white border-amber-600 font-bold shadow-xs'
                              : 'bg-white text-slate-700 border-slate-300 hover:bg-amber-100/50'
                          }`}
                        >
                          {cand.brand_name || cand.product_name}
                        </button>
                      ))}
                    </div>
                  )}
                </div>
              )}

              {result.match_state === 'POSSIBLE_MATCH_NEEDS_REVIEW' && (
                <div className="p-3 bg-amber-50 border border-amber-200 rounded-lg text-xs text-amber-800 space-y-1">
                  <div className="font-bold flex items-center gap-1">
                    <span>⚠️</span> Verification Required Before Lookup
                  </div>
                  <p className="text-[11px]">
                    {result.reasons[0] || 'Low confidence OCR requires confirmation before product suggestions.'}
                  </p>
                </div>
              )}

              {result.match_state === 'NO_RELIABLE_MATCH' && (
                <div className="p-6 text-center space-y-2 bg-surface-50 rounded-lg border border-dashed border-border-light">
                  <span className="text-3xl">📦</span>
                  <h4 className="font-bold text-text-primary text-sm">Product details unavailable</h4>
                  <p className="text-xs text-text-muted max-w-sm mx-auto">
                    {result.reasons[0] || 'No verified catalog entry matched the exact formulation and strength.'}
                  </p>
                  <p className="text-[11px] text-text-muted italic">
                    Safety guard: The system refuses to guess product images or links for unmatched items.
                  </p>
                </div>
              )}

              {/* Product Specifications & Details Card */}
              {selectedProduct && result.match_state !== 'NO_RELIABLE_MATCH' && (
                <div className="border border-border-light rounded-lg p-4 bg-white space-y-3.5">
                  <div className="flex items-start justify-between gap-3">
                    <div>
                      <h4 className="font-bold text-text-primary text-base">
                        {selectedProduct.product_name}
                      </h4>
                      <p className="text-xs text-text-secondary mt-0.5">
                        Manufactured by <strong>{selectedProduct.manufacturer}</strong>
                      </p>
                    </div>
                    {selectedProduct.is_prescription_only ? (
                      <span className="badge badge-warning text-[10px] whitespace-nowrap">
                        Rx Required (Schedule H)
                      </span>
                    ) : (
                      <span className="badge badge-success text-[10px] whitespace-nowrap">
                        OTC Available
                      </span>
                    )}
                  </div>

                  {/* Attributes Grid */}
                  <div className="grid grid-cols-2 gap-2 text-xs pt-1 border-t border-border-light/60">
                    <div>
                      <span className="text-text-muted">Active Ingredient:</span>{' '}
                      <span className="font-semibold text-text-primary">{selectedProduct.active_ingredient}</span>
                    </div>
                    <div>
                      <span className="text-text-muted">Strength:</span>{' '}
                      <span className="font-semibold text-text-primary">{selectedProduct.strength}</span>
                    </div>
                    <div>
                      <span className="text-text-muted">Dosage Form:</span>{' '}
                      <span className="capitalize font-semibold text-text-primary">{selectedProduct.dosage_form}</span>
                    </div>
                    <div>
                      <span className="text-text-muted">Pack Size:</span>{' '}
                      <span className="font-semibold text-text-primary">{selectedProduct.pack_size || 'Standard Pack'}</span>
                    </div>
                    {selectedProduct.country_region && (
                      <div>
                        <span className="text-text-muted">Market/Region:</span>{' '}
                        <span className="font-semibold text-text-primary">{selectedProduct.country_region} (CDSCO / NLEM)</span>
                      </div>
                    )}
                    {selectedProduct.last_checked && (
                      <div>
                        <span className="text-text-muted">Verified As Of:</span>{' '}
                        <span className="text-text-secondary">{new Date(selectedProduct.last_checked).toLocaleDateString()}</span>
                      </div>
                    )}
                  </div>

                  {/* Medical Device Specifications */}
                  {selectedProduct.device_specifications && (
                    <div className="mt-2 p-3 bg-surface-50 rounded text-xs space-y-1 border border-border-light">
                      <div className="font-bold text-text-secondary text-[11px] uppercase tracking-wider">
                        Device Technical Specifications
                      </div>
                      {Object.entries(selectedProduct.device_specifications).map(([k, v]) => (
                        <div key={k} className="flex justify-between text-[11px]">
                          <span className="text-text-muted capitalize">{k.replace(/_/g, ' ')}:</span>
                          <span className="font-medium text-text-primary">{String(v)}</span>
                        </div>
                      ))}
                    </div>
                  )}

                  {/* PROMINENT TABLET PACKAGING IMAGE (Directly visible on View More) */}
                  <div className="pt-2 border-t border-border-light/60 space-y-2">
                    <div className="flex items-center justify-between">
                      <span className="text-xs font-bold text-text-secondary flex items-center gap-1.5">
                        <span>🖼️</span> Tablet & Packaging Image / மாத்திரை புகைப்படம்
                      </span>
                      <button
                        onClick={() => setShowImage(!showImage)}
                        className="text-[11px] text-text-muted hover:text-text-primary underline cursor-pointer"
                      >
                        {showImage ? 'Hide image' : 'Show image'}
                      </button>
                    </div>

                    {showImage && (
                      <div className="space-y-2 animate-in fade-in duration-200">
                        <div className="p-4 bg-slate-50/80 rounded-xl flex flex-col items-center justify-center border border-border-light relative overflow-hidden">
                          {!imageFailed && selectedProduct.product_image_url ? (
                            <img
                              src={selectedProduct.product_image_url}
                              alt={selectedProduct.image_provenance?.alt_text || selectedProduct.product_name}
                              className="max-h-52 w-auto rounded-lg object-contain bg-white p-3 shadow-md border border-slate-200"
                              onError={() => setImageFailed(true)}
                            />
                          ) : (
                            /* High-fidelity tablet packaging visualizer mockup */
                            <div className="w-full max-w-sm bg-gradient-to-br from-slate-100 to-white rounded-lg p-4 border border-slate-300 shadow-sm text-center space-y-2">
                              <div className="inline-block px-2 py-0.5 bg-blue-100 text-blue-800 text-[10px] font-bold rounded">
                                CDSCO / NLEM Reg. Formulation
                              </div>
                              <div className="flex items-center justify-center gap-2 text-primary-700">
                                <span className="text-3xl">💊</span>
                                <div className="text-left">
                                  <div className="font-extrabold text-sm text-slate-800 leading-tight">
                                    {selectedProduct.brand_name || selectedProduct.product_name}
                                  </div>
                                  <div className="text-xs text-slate-600 font-medium">
                                    {selectedProduct.active_ingredient} {selectedProduct.strength}
                                  </div>
                                </div>
                              </div>
                              <div className="text-[10px] text-slate-500 pt-1 border-t border-slate-200 flex justify-between">
                                <span>{selectedProduct.dosage_form.toUpperCase()}</span>
                                <span>{selectedProduct.pack_size || '10/15 Tablets Strip'}</span>
                                <span>{selectedProduct.manufacturer}</span>
                              </div>
                            </div>
                          )}

                          {selectedProduct.image_provenance && (
                            <p className="text-[10px] text-text-muted mt-2 text-center">
                              Source: {selectedProduct.image_provenance.source}
                            </p>
                          )}
                        </div>

                        {/* Mandatory Safety Notice */}
                        <div className="p-2.5 bg-amber-50 rounded-lg border border-amber-200 text-[11px] text-amber-900 leading-relaxed">
                          <strong>Identification Notice:</strong> {result.image_disclaimer}
                        </div>
                      </div>
                    )}
                  </div>

                  {/* CLINICAL DOSAGE & USAGE SUGGESTIONS CARD (Evolo eduthukanum / Epo eduthukanum) */}
                  {selectedProduct.dosage_suggestions && (
                    <div className="p-4 bg-teal-50/80 rounded-xl border border-teal-200 space-y-3">
                      <div className="flex items-center justify-between">
                        <span className="text-xs font-bold text-teal-950 flex items-center gap-1.5 uppercase tracking-wide">
                          <span>💊</span> Clinical Dosage & Usage Guidance / பயன்பாட்டு வழிகாட்டல்
                        </span>
                        <span className="text-[10px] bg-teal-100 text-teal-800 font-semibold px-2 py-0.5 rounded-full border border-teal-300">
                          NLEM Standard Reference
                        </span>
                      </div>

                      <div className="grid grid-cols-1 sm:grid-cols-2 gap-2.5 text-xs">
                        {selectedProduct.dosage_suggestions.how_much && (
                          <div className="p-2.5 bg-white rounded-lg border border-teal-200 shadow-2xs">
                            <span className="text-text-muted text-[10px] font-semibold block uppercase">
                              🥄 How Much to Take / எவ்வளவு எடுக்க வேண்டும்
                            </span>
                            <strong className="text-teal-950 text-xs mt-0.5 block font-semibold">
                              {selectedProduct.dosage_suggestions.how_much}
                            </strong>
                          </div>
                        )}
                        {(selectedProduct.dosage_suggestions.when || selectedProduct.dosage_suggestions.when_to_take) && (
                          <div className="p-2.5 bg-white rounded-lg border border-teal-200 shadow-2xs">
                            <span className="text-text-muted text-[10px] font-semibold block uppercase">
                              ⏰ When to Take / எப்போது எடுக்க வேண்டும்
                            </span>
                            <strong className="text-teal-950 text-xs mt-0.5 block font-semibold">
                              {selectedProduct.dosage_suggestions.when || selectedProduct.dosage_suggestions.when_to_take}
                            </strong>
                          </div>
                        )}
                        {selectedProduct.dosage_suggestions.food && (
                          <div className="p-2.5 bg-white rounded-lg border border-teal-200 shadow-2xs">
                            <span className="text-text-muted text-[10px] font-semibold block uppercase">
                              🍽️ Food Timing / உணவு வழிகாட்டல்
                            </span>
                            <strong className="text-teal-950 text-xs mt-0.5 block font-semibold">
                              {selectedProduct.dosage_suggestions.food}
                            </strong>
                          </div>
                        )}
                        {selectedProduct.dosage_suggestions.duration && (
                          <div className="p-2.5 bg-white rounded-lg border border-teal-200 shadow-2xs">
                            <span className="text-text-muted text-[10px] font-semibold block uppercase">
                              📅 Recommended Duration / கால அளவு
                            </span>
                            <strong className="text-teal-950 text-xs mt-0.5 block font-semibold">
                              {selectedProduct.dosage_suggestions.duration}
                            </strong>
                          </div>
                        )}
                      </div>

                      {selectedProduct.dosage_suggestions.precautions && (
                        <div className="p-2.5 bg-amber-50 rounded-lg border border-amber-200 text-[11px] text-amber-900 leading-relaxed">
                          <strong>⚠️ Precautions & Suggestions / முன்னெச்சரிக்கைகள்: </strong>
                          {selectedProduct.dosage_suggestions.precautions}
                        </div>
                      )}

                      {selectedProduct.dosage_suggestions.tamil_instructions && (
                        <div className="p-2.5 bg-teal-100/70 rounded-lg border border-teal-300 text-[11px] text-teal-950 leading-relaxed font-medium">
                          <strong>தமிழ் வழிகாட்டல்: </strong>
                          {selectedProduct.dosage_suggestions.tamil_instructions}
                        </div>
                      )}
                    </div>
                  )}

                  {/* MULTI-PROVIDER PHARMACY PANEL */}
                  <PharmacyProviders
                    medicineName={selectedProduct.product_name}
                    brandName={selectedProduct.brand_name}
                    genericName={selectedProduct.active_ingredient}
                    isPrescriptionOnly={selectedProduct.is_prescription_only}
                  />
                </div>
              )}

              {/* General Disclaimer */}
              <p className="text-[10px] text-text-muted text-center pt-2 border-t border-border-light">
                {result.general_disclaimer}
              </p>
            </div>
          )}
        </div>

        {/* Modal Footer */}
        <div className="px-5 py-3 bg-surface-50 border-t border-border-light flex justify-end">
          <button onClick={onClose} className="btn btn-secondary text-xs px-4 py-1.5">
            Close
          </button>
        </div>
      </div>
    </div>
  );
};
export default ProductDetailsModal;

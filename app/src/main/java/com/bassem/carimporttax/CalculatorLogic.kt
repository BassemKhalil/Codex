package com.bassem.carimporttax

/**
 * Pure calculation logic for Lebanese vehicle import duties and taxes.
 *
 * Standard structure for a petrol / diesel passenger car (confirmed against the
 * official customs calculator at customs.gov.lb and the 2024 budget law):
 *   - Customs duty            5%   of the customs value
 *   - Excise / consumption   45%   of the customs value
 *   - VAT                    11%   of (customs value + duties)
 *   - Optional additional     3%   customs fee (depends on the budget law in force)
 *
 * Green-vehicle incentives (2024 budget law, Article 69):
 *   - Fully electric: customs duty AND excise are fully exempt; registration /
 *     mecanique reduced by 70%. VAT still applies.
 *   - Hybrid:         customs duty AND excise reduced by 80%; registration /
 *     mecanique reduced by 70%. VAT still applies.
 *
 * These are modelled as multipliers on the standard rates the user sees, so the
 * 5% / 45% fields keep their plain meaning and the incentive is applied on top.
 *
 * Lebanese customs values used cars on published Blue Book / Schwacke figures,
 * so the value entered by the user is treated as the customs basis. The CIF
 * option additionally folds shipping and insurance into that basis.
 *
 * All amounts are in USD. The exchange rate is used only to display the
 * Lebanese pound equivalents and never affects the USD figures, which are
 * percentage based on a USD value.
 */

enum class VehicleType { PETROL, HYBRID, ELECTRIC }

/** Fraction of customs duty + excise actually paid for each vehicle type. */
val VehicleType.dutyFactor: Double
    get() = when (this) {
        VehicleType.PETROL -> 1.0    // full duties
        VehicleType.HYBRID -> 0.20   // 80% reduction
        VehicleType.ELECTRIC -> 0.0  // fully exempt
    }

/** Fraction of registration / mecanique actually paid for each vehicle type. */
val VehicleType.registrationFactor: Double
    get() = when (this) {
        VehicleType.PETROL -> 1.0                          // full registration
        VehicleType.HYBRID, VehicleType.ELECTRIC -> 0.30   // 70% reduction
    }

data class ImportInputs(
    val vehicleValue: Double,
    val vehicleType: VehicleType,
    val customsRate: Double,
    val exciseRate: Double,
    val vatRate: Double,
    val additionalFeeEnabled: Boolean,
    val additionalFeeRate: Double,
    val dutiesOnCif: Boolean,
    val shipping: Double,
    val insurance: Double,
    val broker: Double,
    val port: Double,
    val registration: Double,
    val exchangeRate: Double
)

data class ImportResult(
    val customsBase: Double,
    val customsDuty: Double,
    val excise: Double,
    val additionalFee: Double,
    val dutySubtotal: Double,
    val vatBase: Double,
    val vat: Double,
    val totalGovernment: Double,
    val effectiveTaxRate: Double,
    val registrationApplied: Double,
    val totalLogistics: Double,
    val importCost: Double,
    val landedTotal: Double
)

fun calculateImport(i: ImportInputs): ImportResult {
    val customsBase =
        if (i.dutiesOnCif) i.vehicleValue + i.shipping + i.insurance else i.vehicleValue

    // Electric / hybrid relief applies to customs duty and excise only.
    val dutyFactor = i.vehicleType.dutyFactor
    val customsDuty = customsBase * i.customsRate * dutyFactor
    val excise = customsBase * i.exciseRate * dutyFactor
    val additionalFee = if (i.additionalFeeEnabled) customsBase * i.additionalFeeRate else 0.0
    val dutySubtotal = customsDuty + excise + additionalFee

    val vatBase = customsBase + dutySubtotal
    val vat = vatBase * i.vatRate

    val totalGovernment = dutySubtotal + vat
    val effectiveTaxRate = if (i.vehicleValue > 0.0) totalGovernment / i.vehicleValue else 0.0

    // Registration / mecanique gets the 70% green-vehicle reduction.
    val registrationApplied = i.registration * i.vehicleType.registrationFactor

    val totalLogistics = i.shipping + i.insurance + i.broker + i.port + registrationApplied
    val importCost = totalGovernment + totalLogistics
    val landedTotal = i.vehicleValue + importCost

    return ImportResult(
        customsBase = customsBase,
        customsDuty = customsDuty,
        excise = excise,
        additionalFee = additionalFee,
        dutySubtotal = dutySubtotal,
        vatBase = vatBase,
        vat = vat,
        totalGovernment = totalGovernment,
        effectiveTaxRate = effectiveTaxRate,
        registrationApplied = registrationApplied,
        totalLogistics = totalLogistics,
        importCost = importCost,
        landedTotal = landedTotal
    )
}

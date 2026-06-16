package com.bassem.carimporttax

/**
 * Pure calculation logic for Lebanese vehicle import duties and taxes.
 *
 * Standard structure for passenger cars:
 *   - Customs duty            5%   of the customs value
 *   - Excise / consumption   45%   of the customs value
 *   - VAT                    11%   of (customs value + duties)
 *   - Optional additional     3%   customs fee (depends on the budget law in force)
 *
 * Lebanese customs values used cars on published Blue Book / Schwacke figures,
 * so the value entered by the user is treated as the customs basis. The CIF
 * option additionally folds shipping and insurance into that basis.
 *
 * All amounts are in USD. The exchange rate is used only to display the
 * Lebanese pound equivalents and never affects the USD figures, which are
 * percentage based on a USD value.
 */

data class ImportInputs(
    val vehicleValue: Double,
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
    val totalLogistics: Double,
    val importCost: Double,
    val landedTotal: Double
)

fun calculateImport(i: ImportInputs): ImportResult {
    val customsBase =
        if (i.dutiesOnCif) i.vehicleValue + i.shipping + i.insurance else i.vehicleValue

    val customsDuty = customsBase * i.customsRate
    val excise = customsBase * i.exciseRate
    val additionalFee = if (i.additionalFeeEnabled) customsBase * i.additionalFeeRate else 0.0
    val dutySubtotal = customsDuty + excise + additionalFee

    val vatBase = customsBase + dutySubtotal
    val vat = vatBase * i.vatRate

    val totalGovernment = dutySubtotal + vat
    val effectiveTaxRate = if (i.vehicleValue > 0.0) totalGovernment / i.vehicleValue else 0.0

    val totalLogistics = i.shipping + i.insurance + i.broker + i.port + i.registration
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
        totalLogistics = totalLogistics,
        importCost = importCost,
        landedTotal = landedTotal
    )
}

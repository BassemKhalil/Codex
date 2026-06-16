package com.bassem.carimporttax

import android.os.Bundle
import androidx.activity.ComponentActivity
import androidx.activity.compose.setContent
import androidx.activity.enableEdgeToEdge
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.PaddingValues
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.text.KeyboardOptions
import androidx.compose.foundation.verticalScroll
import androidx.compose.material3.Card
import androidx.compose.material3.CardDefaults
import androidx.compose.material3.ExperimentalMaterial3Api
import androidx.compose.material3.HorizontalDivider
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.OutlinedTextField
import androidx.compose.material3.Scaffold
import androidx.compose.material3.SegmentedButton
import androidx.compose.material3.SegmentedButtonDefaults
import androidx.compose.material3.SingleChoiceSegmentedButtonRow
import androidx.compose.material3.Switch
import androidx.compose.material3.Tab
import androidx.compose.material3.TabRow
import androidx.compose.material3.Text
import androidx.compose.material3.TopAppBar
import androidx.compose.material3.TopAppBarDefaults
import androidx.compose.runtime.Composable
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.saveable.rememberSaveable
import androidx.compose.runtime.setValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.text.input.KeyboardType
import androidx.compose.ui.tooling.preview.Preview
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import com.bassem.carimporttax.ui.theme.CarImportTaxTheme
import java.text.NumberFormat
import java.util.Locale

class MainActivity : ComponentActivity() {
    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        enableEdgeToEdge()
        setContent {
            CarImportTaxTheme {
                MainScreen()
            }
        }
    }
}

// ---- Formatting helpers ----

private val groupedFormat: NumberFormat =
    NumberFormat.getNumberInstance(Locale.US).apply { maximumFractionDigits = 0 }

private fun usd(value: Double): String = "$" + groupedFormat.format(value)
private fun lbp(value: Double): String = "LBP " + groupedFormat.format(value)
private fun pct(rate: Double): String = String.format(Locale.US, "%.1f%%", rate * 100.0)

private fun String.toDoubleOrZero(): Double =
    this.replace(",", "").trim().toDoubleOrNull() ?: 0.0

// ---- Top-level screen with tabs ----

@OptIn(ExperimentalMaterial3Api::class)
@Composable
fun MainScreen() {
    var selectedTab by rememberSaveable { mutableStateOf(0) }
    val tabs = listOf("Calculator", "Guide")

    Scaffold(
        topBar = {
            Column {
                TopAppBar(
                    title = {
                        Text("Lebanon Car Import Tax", fontWeight = FontWeight.SemiBold)
                    },
                    colors = TopAppBarDefaults.topAppBarColors(
                        containerColor = MaterialTheme.colorScheme.primary,
                        titleContentColor = MaterialTheme.colorScheme.onPrimary
                    )
                )
                TabRow(
                    selectedTabIndex = selectedTab,
                    containerColor = MaterialTheme.colorScheme.primary,
                    contentColor = MaterialTheme.colorScheme.onPrimary
                ) {
                    tabs.forEachIndexed { index, title ->
                        Tab(
                            selected = selectedTab == index,
                            onClick = { selectedTab = index },
                            text = { Text(title) }
                        )
                    }
                }
            }
        }
    ) { innerPadding ->
        if (selectedTab == 0) {
            CalculatorTab(innerPadding)
        } else {
            GuideTab(innerPadding)
        }
    }
}

// ---- Calculator tab ----

@Composable
fun CalculatorTab(innerPadding: PaddingValues) {
    // Defaults reproduce the worked 2021 Porsche Macan Turbo example.
    // rememberSaveable keeps inputs intact while you flip to the Guide tab and back.
    var value by rememberSaveable { mutableStateOf("48600") }
    var vehicleType by rememberSaveable { mutableStateOf(VehicleType.PETROL) }
    var customs by rememberSaveable { mutableStateOf("5") }
    var excise by rememberSaveable { mutableStateOf("45") }
    var vat by rememberSaveable { mutableStateOf("11") }
    var addFeeOn by rememberSaveable { mutableStateOf(false) }
    var addFeeRate by rememberSaveable { mutableStateOf("3") }
    var cifBasis by rememberSaveable { mutableStateOf(false) }
    var shipping by rememberSaveable { mutableStateOf("2500") }
    var insurance by rememberSaveable { mutableStateOf("400") }
    var broker by rememberSaveable { mutableStateOf("450") }
    var port by rememberSaveable { mutableStateOf("300") }
    var registration by rememberSaveable { mutableStateOf("1000") }
    var fx by rememberSaveable { mutableStateOf("89500") }

    val inputs = ImportInputs(
        vehicleValue = value.toDoubleOrZero(),
        vehicleType = vehicleType,
        customsRate = customs.toDoubleOrZero() / 100.0,
        exciseRate = excise.toDoubleOrZero() / 100.0,
        vatRate = vat.toDoubleOrZero() / 100.0,
        additionalFeeEnabled = addFeeOn,
        additionalFeeRate = addFeeRate.toDoubleOrZero() / 100.0,
        dutiesOnCif = cifBasis,
        shipping = shipping.toDoubleOrZero(),
        insurance = insurance.toDoubleOrZero(),
        broker = broker.toDoubleOrZero(),
        port = port.toDoubleOrZero(),
        registration = registration.toDoubleOrZero(),
        exchangeRate = fx.toDoubleOrZero()
    )
    val result = calculateImport(inputs)

    Column(
        modifier = Modifier
            .padding(innerPadding)
            .verticalScroll(rememberScrollState())
            .padding(16.dp),
        verticalArrangement = Arrangement.spacedBy(16.dp)
    ) {
        SummaryCard(result)

        SectionCard("Vehicle") {
            MoneyField("Blue Book / Schwacke value", value) { value = it }
            Text(
                "Customs values used cars on these published figures, so enter that here.",
                style = MaterialTheme.typography.bodySmall,
                color = MaterialTheme.colorScheme.onSurfaceVariant
            )
            Spacer(Modifier.height(4.dp))
            Text("Vehicle type", style = MaterialTheme.typography.bodyMedium)
            VehicleTypeSelector(vehicleType) { vehicleType = it }
            Text(
                vehicleTypeNote(vehicleType),
                style = MaterialTheme.typography.bodySmall,
                color = MaterialTheme.colorScheme.onSurfaceVariant
            )
        }

        SectionCard("Duty and tax rates") {
            PercentField("Customs duty", customs) { customs = it }
            PercentField("Excise / consumption tax", excise) { excise = it }
            PercentField("VAT", vat) { vat = it }
            SwitchRow("Add 3% additional customs fee", addFeeOn) { addFeeOn = it }
            if (addFeeOn) {
                PercentField("Additional fee", addFeeRate) { addFeeRate = it }
            }
            SwitchRow(
                "Charge duties on CIF (adds shipping + insurance to the base)",
                cifBasis
            ) { cifBasis = it }
        }

        SectionCard("Shipping and clearance") {
            MoneyField("Shipping (RoRo / container)", shipping) { shipping = it }
            MoneyField("Marine insurance", insurance) { insurance = it }
            MoneyField("Customs broker / clearance", broker) { broker = it }
            MoneyField("Port handling", port) { port = it }
            MoneyField("Registration + plates", registration) { registration = it }
        }

        SectionCard("Breakdown") {
            BreakdownRows(result, inputs)
        }

        SectionCard("Lebanese pound (optional)") {
            NumberField("Exchange rate (LBP per USD)", fx) { fx = it }
            Spacer(Modifier.height(4.dp))
            LineItem("Total duties and VAT", lbp(result.totalGovernment * inputs.exchangeRate))
            LineItem(
                "All-in landed",
                lbp(result.landedTotal * inputs.exchangeRate),
                bold = true
            )
        }

        Text(
            "Estimates only. Rates reflect the standard 5% customs + 45% excise + 11% VAT " +
                "structure; the 3% additional customs fee depends on the budget law in force. " +
                "Electric and hybrid relief follows the 2024 budget law. Confirm the exact " +
                "figure with a licensed broker or the official calculator at customs.gov.lb.",
            style = MaterialTheme.typography.bodySmall,
            color = MaterialTheme.colorScheme.onSurfaceVariant
        )

        Spacer(Modifier.height(24.dp))
    }
}

private fun vehicleTypeNote(type: VehicleType): String = when (type) {
    VehicleType.PETROL ->
        "Petrol / diesel: full customs duty and excise apply."
    VehicleType.HYBRID ->
        "Hybrid (2024 budget): customs duty and excise reduced 80%, registration reduced 70%."
    VehicleType.ELECTRIC ->
        "Fully electric (2024 budget): customs duty and excise exempt, registration reduced 70%. VAT still applies."
}

// ---- Components ----

@OptIn(ExperimentalMaterial3Api::class)
@Composable
private fun VehicleTypeSelector(selected: VehicleType, onSelect: (VehicleType) -> Unit) {
    val options = listOf(
        VehicleType.PETROL to "Petrol / Diesel",
        VehicleType.HYBRID to "Hybrid",
        VehicleType.ELECTRIC to "Electric"
    )
    SingleChoiceSegmentedButtonRow(modifier = Modifier.fillMaxWidth()) {
        options.forEachIndexed { index, (type, label) ->
            SegmentedButton(
                selected = selected == type,
                onClick = { onSelect(type) },
                shape = SegmentedButtonDefaults.itemShape(index = index, count = options.size)
            ) {
                Text(label, style = MaterialTheme.typography.labelLarge)
            }
        }
    }
}

@Composable
private fun SummaryCard(result: ImportResult) {
    Card(
        modifier = Modifier.fillMaxWidth(),
        colors = CardDefaults.cardColors(
            containerColor = MaterialTheme.colorScheme.primaryContainer,
            contentColor = MaterialTheme.colorScheme.onPrimaryContainer
        )
    ) {
        Column(
            modifier = Modifier.padding(20.dp),
            verticalArrangement = Arrangement.spacedBy(4.dp)
        ) {
            Text("All-in landed cost", style = MaterialTheme.typography.labelLarge)
            Text(
                usd(result.landedTotal),
                fontSize = 34.sp,
                fontWeight = FontWeight.Bold
            )
            Spacer(Modifier.height(10.dp))
            Row(
                modifier = Modifier.fillMaxWidth(),
                horizontalArrangement = Arrangement.SpaceBetween
            ) {
                Column {
                    Text("Import cost", style = MaterialTheme.typography.labelMedium)
                    Text(usd(result.importCost), fontWeight = FontWeight.SemiBold)
                }
                Column(horizontalAlignment = Alignment.End) {
                    Text("Effective tax", style = MaterialTheme.typography.labelMedium)
                    Text(pct(result.effectiveTaxRate), fontWeight = FontWeight.SemiBold)
                }
            }
        }
    }
}

@Composable
private fun SectionCard(
    title: String,
    content: @Composable () -> Unit
) {
    Card(modifier = Modifier.fillMaxWidth()) {
        Column(
            modifier = Modifier.padding(16.dp),
            verticalArrangement = Arrangement.spacedBy(12.dp)
        ) {
            Text(
                title,
                style = MaterialTheme.typography.titleMedium,
                fontWeight = FontWeight.SemiBold
            )
            content()
        }
    }
}

@Composable
private fun MoneyField(label: String, value: String, onChange: (String) -> Unit) {
    OutlinedTextField(
        value = value,
        onValueChange = { onChange(it.filter { c -> c.isDigit() || c == '.' }) },
        label = { Text(label) },
        leadingIcon = { Text("$") },
        singleLine = true,
        keyboardOptions = KeyboardOptions(keyboardType = KeyboardType.Decimal),
        modifier = Modifier.fillMaxWidth()
    )
}

@Composable
private fun PercentField(label: String, value: String, onChange: (String) -> Unit) {
    OutlinedTextField(
        value = value,
        onValueChange = { onChange(it.filter { c -> c.isDigit() || c == '.' }) },
        label = { Text(label) },
        trailingIcon = { Text("%") },
        singleLine = true,
        keyboardOptions = KeyboardOptions(keyboardType = KeyboardType.Decimal),
        modifier = Modifier.fillMaxWidth()
    )
}

@Composable
private fun NumberField(label: String, value: String, onChange: (String) -> Unit) {
    OutlinedTextField(
        value = value,
        onValueChange = { onChange(it.filter { c -> c.isDigit() || c == '.' }) },
        label = { Text(label) },
        singleLine = true,
        keyboardOptions = KeyboardOptions(keyboardType = KeyboardType.Decimal),
        modifier = Modifier.fillMaxWidth()
    )
}

@Composable
private fun SwitchRow(label: String, checked: Boolean, onChange: (Boolean) -> Unit) {
    Row(
        modifier = Modifier.fillMaxWidth(),
        verticalAlignment = Alignment.CenterVertically
    ) {
        Text(
            label,
            modifier = Modifier.weight(1f),
            style = MaterialTheme.typography.bodyMedium
        )
        Switch(checked = checked, onCheckedChange = onChange)
    }
}

@Composable
private fun LineItem(
    label: String,
    amount: String,
    bold: Boolean = false,
    emphasized: Boolean = false
) {
    Row(
        modifier = Modifier
            .fillMaxWidth()
            .padding(vertical = 2.dp),
        horizontalArrangement = Arrangement.SpaceBetween
    ) {
        Text(
            label,
            style = MaterialTheme.typography.bodyMedium,
            fontWeight = if (bold) FontWeight.Bold else FontWeight.Normal
        )
        Text(
            amount,
            style = MaterialTheme.typography.bodyMedium,
            fontWeight = if (bold) FontWeight.Bold else FontWeight.Normal,
            color = if (emphasized) MaterialTheme.colorScheme.primary else Color.Unspecified
        )
    }
}

@Composable
private fun BreakdownRows(result: ImportResult, inputs: ImportInputs) {
    val reduced = inputs.vehicleType != VehicleType.PETROL
    val dutyTag = when (inputs.vehicleType) {
        VehicleType.PETROL -> ""
        VehicleType.HYBRID -> " −80%"
        VehicleType.ELECTRIC -> " exempt"
    }
    Column(verticalArrangement = Arrangement.spacedBy(2.dp)) {
        LineItem("Vehicle value", usd(inputs.vehicleValue))
        if (inputs.dutiesOnCif) {
            LineItem("Customs base (CIF)", usd(result.customsBase))
        }
        HorizontalDivider(Modifier.padding(vertical = 6.dp))

        LineItem("Customs duty (${pct(inputs.customsRate)}$dutyTag)", usd(result.customsDuty))
        LineItem("Excise / consumption (${pct(inputs.exciseRate)}$dutyTag)", usd(result.excise))
        if (inputs.additionalFeeEnabled) {
            LineItem(
                "Additional customs fee (${pct(inputs.additionalFeeRate)})",
                usd(result.additionalFee)
            )
        }
        LineItem("VAT (${pct(inputs.vatRate)})", usd(result.vat))
        LineItem(
            "Total duties and VAT",
            usd(result.totalGovernment),
            bold = true,
            emphasized = true
        )
        HorizontalDivider(Modifier.padding(vertical = 6.dp))

        LineItem("Shipping", usd(inputs.shipping))
        LineItem("Insurance", usd(inputs.insurance))
        LineItem("Broker / clearance", usd(inputs.broker))
        LineItem("Port handling", usd(inputs.port))
        LineItem(
            "Registration + plates" + if (reduced) " (−70%)" else "",
            usd(result.registrationApplied)
        )
        LineItem("Total logistics and fees", usd(result.totalLogistics), bold = true)
        HorizontalDivider(Modifier.padding(vertical = 6.dp))

        LineItem("Import cost (on top of car)", usd(result.importCost), bold = true)
        LineItem(
            "All-in landed total",
            usd(result.landedTotal),
            bold = true,
            emphasized = true
        )
    }
}

// ---- Guide tab ----

@Composable
fun GuideTab(innerPadding: PaddingValues) {
    Column(
        modifier = Modifier
            .padding(innerPadding)
            .verticalScroll(rememberScrollState())
            .padding(16.dp),
        verticalArrangement = Arrangement.spacedBy(16.dp)
    ) {
        GuideCard("What this app does") {
            GuideText(
                "It estimates the all-in cost of importing a car into Lebanon: the " +
                    "government duties and taxes plus the shipping and clearance costs. " +
                    "Everything recalculates live as you type, and every rate is editable, " +
                    "so it works for any vehicle — not just the example it opens with."
            )
        }

        GuideCard("How Lebanon taxes an imported car") {
            GuideText(
                "Lebanese customs do not use your invoice. They value the car from " +
                    "published Blue Book / Schwacke catalogues and apply duties to that " +
                    "\"customs value\". On a standard petrol or diesel passenger car:"
            )
            GuideBullet("Customs duty — 5% of the customs value.")
            GuideBullet("Excise / consumption tax (رسم استهلاك) — 45% of the customs value.")
            GuideBullet("VAT (TVA) — 11%, charged on the value plus the duties above.")
            GuideBullet(
                "Additional customs fee — 3%, an extra fee on VAT-able imports that " +
                    "successive budget laws keep re-extending, so it is optional here."
            )
            GuideText(
                "Duties and VAT together come to roughly 66% of the car's value at the " +
                    "default rates. Registration / mecanique and the shipping and clearance " +
                    "costs are on top."
            )
        }

        GuideCard("Vehicle type: petrol, hybrid, electric") {
            GuideText(
                "The 2024 budget law (Article 69) gives green vehicles large relief. " +
                    "Pick the type and the app adjusts the duties for you:"
            )
            GuideBullet("Petrol / Diesel — full customs duty and excise.")
            GuideBullet(
                "Hybrid — customs duty and excise reduced by 80%, and registration / " +
                    "mecanique reduced by 70%. VAT still applies."
            )
            GuideBullet(
                "Electric — customs duty and excise fully exempt, and registration / " +
                    "mecanique reduced by 70%. VAT still applies."
            )
            GuideText(
                "The relief is applied on top of the rate fields, so the 5% / 45% boxes " +
                    "keep their plain meaning and the breakdown shows the reduction."
            )
        }

        GuideCard("Every input field, explained") {
            GuideField(
                "Blue Book / Schwacke value",
                "The catalogue value of the car. This is the customs base — the number " +
                    "all the percentage duties are calculated from."
            )
            GuideField(
                "Vehicle type",
                "Petrol/Diesel, Hybrid or Electric. Controls the green-vehicle relief " +
                    "described above."
            )
            GuideField(
                "Customs duty %",
                "The customs duty rate. Default 5% for passenger cars."
            )
            GuideField(
                "Excise / consumption tax %",
                "The local consumption tax (رسم استهلاك). Default 45%."
            )
            GuideField(
                "VAT %",
                "Value-added tax (TVA), default 11%. It is charged on the customs value " +
                    "plus the duties, not on the value alone."
            )
            GuideField(
                "Add 3% additional customs fee",
                "Turns on the extra 3% fee that applies in years the budget law renews it. " +
                    "Off by default; switch it on if it is in force."
            )
            GuideField(
                "Charge duties on CIF",
                "When on, shipping and insurance are folded into the customs base before " +
                    "duties are applied (Cost + Insurance + Freight), which raises the duty " +
                    "slightly. When off, duties are on the car value only."
            )
            GuideField(
                "Shipping (RoRo / container)",
                "What you pay to ship the car — roll-on/roll-off or container."
            )
            GuideField("Marine insurance", "Insurance covering the car in transit.")
            GuideField(
                "Customs broker / clearance",
                "The broker's fee for clearing the car through customs."
            )
            GuideField("Port handling", "Port and terminal handling charges in Lebanon.")
            GuideField(
                "Registration + plates",
                "One-off cost to register the car and issue plates (تسجيل / ميكانيك). " +
                    "Hybrid and electric cars get 70% off this."
            )
            GuideField(
                "Exchange rate (LBP per USD)",
                "Only used to show Lebanese-pound equivalents. It never changes the USD " +
                    "figures, which are all percentage-based."
            )
        }

        GuideCard("Reading the results") {
            GuideField(
                "All-in landed cost",
                "The big number at the top: the car value plus every duty, tax and fee."
            )
            GuideField(
                "Import cost",
                "Everything on top of the car — duties, VAT and logistics combined."
            )
            GuideField(
                "Effective tax",
                "Total duties and VAT as a percentage of the car's value, so you can " +
                    "compare cars at a glance."
            )
            GuideField(
                "Breakdown",
                "Line-by-line: each duty and fee, the government subtotal, the logistics " +
                    "subtotal, and the landed total."
            )
        }

        GuideCard("Important notes") {
            GuideBullet(
                "These are estimates. Customs valuation, the exact catalogue figure and " +
                    "the fees in force can move the real number."
            )
            GuideBullet(
                "The 3% additional fee and the green-vehicle relief depend on the budget " +
                    "law in force in the year you import."
            )
            GuideBullet(
                "Always confirm with a licensed customs broker or the official calculator " +
                    "at customs.gov.lb before committing."
            )
        }

        Spacer(Modifier.height(24.dp))
    }
}

@Composable
private fun GuideCard(title: String, content: @Composable () -> Unit) {
    Card(modifier = Modifier.fillMaxWidth()) {
        Column(
            modifier = Modifier.padding(16.dp),
            verticalArrangement = Arrangement.spacedBy(8.dp)
        ) {
            Text(
                title,
                style = MaterialTheme.typography.titleMedium,
                fontWeight = FontWeight.SemiBold,
                color = MaterialTheme.colorScheme.primary
            )
            content()
        }
    }
}

@Composable
private fun GuideText(text: String) {
    Text(text, style = MaterialTheme.typography.bodyMedium)
}

@Composable
private fun GuideBullet(text: String) {
    Row(horizontalArrangement = Arrangement.spacedBy(8.dp)) {
        Text("•", style = MaterialTheme.typography.bodyMedium)
        Text(text, style = MaterialTheme.typography.bodyMedium)
    }
}

@Composable
private fun GuideField(name: String, description: String) {
    Column(verticalArrangement = Arrangement.spacedBy(2.dp)) {
        Text(name, style = MaterialTheme.typography.bodyMedium, fontWeight = FontWeight.SemiBold)
        Text(
            description,
            style = MaterialTheme.typography.bodySmall,
            color = MaterialTheme.colorScheme.onSurfaceVariant
        )
    }
}

@Preview(showBackground = true)
@Composable
private fun MainScreenPreview() {
    CarImportTaxTheme {
        MainScreen()
    }
}

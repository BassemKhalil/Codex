package com.bassem.carimporttax

import android.os.Bundle
import androidx.activity.ComponentActivity
import androidx.activity.compose.setContent
import androidx.activity.enableEdgeToEdge
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Column
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
import androidx.compose.material3.Switch
import androidx.compose.material3.Text
import androidx.compose.material3.TopAppBar
import androidx.compose.material3.TopAppBarDefaults
import androidx.compose.runtime.Composable
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
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
                CalculatorScreen()
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

// ---- Screen ----

@OptIn(ExperimentalMaterial3Api::class)
@Composable
fun CalculatorScreen() {
    // Defaults reproduce the worked 2021 Porsche Macan Turbo example.
    var value by remember { mutableStateOf("48600") }
    var customs by remember { mutableStateOf("5") }
    var excise by remember { mutableStateOf("45") }
    var vat by remember { mutableStateOf("11") }
    var addFeeOn by remember { mutableStateOf(false) }
    var addFeeRate by remember { mutableStateOf("3") }
    var cifBasis by remember { mutableStateOf(false) }
    var shipping by remember { mutableStateOf("2500") }
    var insurance by remember { mutableStateOf("400") }
    var broker by remember { mutableStateOf("450") }
    var port by remember { mutableStateOf("300") }
    var registration by remember { mutableStateOf("1000") }
    var fx by remember { mutableStateOf("89500") }

    val inputs = ImportInputs(
        vehicleValue = value.toDoubleOrZero(),
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

    Scaffold(
        topBar = {
            TopAppBar(
                title = {
                    Text(
                        "Lebanon Car Import Tax",
                        fontWeight = FontWeight.SemiBold
                    )
                },
                colors = TopAppBarDefaults.topAppBarColors(
                    containerColor = MaterialTheme.colorScheme.primary,
                    titleContentColor = MaterialTheme.colorScheme.onPrimary
                )
            )
        }
    ) { innerPadding ->
        Column(
            modifier = Modifier
                .padding(innerPadding)
                .verticalScroll(rememberScrollState())
                .padding(16.dp),
            verticalArrangement = Arrangement.spacedBy(16.dp)
        ) {
            SummaryCard(result)

            SectionCard("Vehicle value") {
                MoneyField("Blue Book / Schwacke value", value) { value = it }
                Text(
                    "Customs values used cars on these published figures, so enter that here.",
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
                    "Confirm the exact figure with a licensed broker or the official calculator at " +
                    "customs.gov.lb.",
                style = MaterialTheme.typography.bodySmall,
                color = MaterialTheme.colorScheme.onSurfaceVariant
            )

            Spacer(Modifier.height(24.dp))
        }
    }
}

// ---- Components ----

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
    Column(verticalArrangement = Arrangement.spacedBy(2.dp)) {
        LineItem("Vehicle value", usd(inputs.vehicleValue))
        if (inputs.dutiesOnCif) {
            LineItem("Customs base (CIF)", usd(result.customsBase))
        }
        HorizontalDivider(Modifier.padding(vertical = 6.dp))

        LineItem("Customs duty (${pct(inputs.customsRate)})", usd(result.customsDuty))
        LineItem("Excise / consumption (${pct(inputs.exciseRate)})", usd(result.excise))
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
        LineItem("Registration + plates", usd(inputs.registration))
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

@Preview(showBackground = true)
@Composable
private fun CalculatorScreenPreview() {
    CarImportTaxTheme {
        CalculatorScreen()
    }
}

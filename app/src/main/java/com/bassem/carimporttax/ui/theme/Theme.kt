package com.bassem.carimporttax.ui.theme

import androidx.compose.foundation.isSystemInDarkTheme
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.darkColorScheme
import androidx.compose.material3.lightColorScheme
import androidx.compose.runtime.Composable
import androidx.compose.ui.graphics.Color

private val LightColors = lightColorScheme(
    primary = CedarRed,
    onPrimary = Color.White,
    primaryContainer = LightRedContainer,
    onPrimaryContainer = OnLightRedContainer,
    secondary = CedarGreen,
    onSecondary = Color.White
)

private val DarkColors = darkColorScheme(
    primary = Color(0xFFFFB4AB),
    onPrimary = Color(0xFF690009),
    primaryContainer = Color(0xFF93000F),
    onPrimaryContainer = LightRedContainer,
    secondary = Color(0xFF9ACD9E),
    onSecondary = Color(0xFF003912)
)

@Composable
fun CarImportTaxTheme(
    darkTheme: Boolean = isSystemInDarkTheme(),
    content: @Composable () -> Unit
) {
    val colors = if (darkTheme) DarkColors else LightColors
    MaterialTheme(
        colorScheme = colors,
        typography = AppTypography,
        content = content
    )
}

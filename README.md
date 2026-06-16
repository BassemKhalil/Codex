# Lebanon Car Import Tax

A small native Android app (Kotlin + Jetpack Compose, Material 3) that estimates the
total cost of importing a car into Lebanon. Everything recalculates live as you type.
Blue Book / Schwacke values are entered manually.

## Install on your phone (no desktop needed)

Every push to this repo builds the APK in the cloud with GitHub Actions and attaches it
to a release, so you can install straight from your phone:

1. Open this repo on your phone and go to the **Releases** page (or the **`apk-latest`**
   release directly).
2. Under **Assets**, tap **`LebaneseCarImportTax.apk`** to download it.
3. Tap the downloaded file to install. The first time, Android asks you to allow your
   browser / file manager to "install unknown apps" — enable it, then tap the APK again.

That's it — no Android Studio, no cable, no computer. The same APK is also published as
the **`LebaneseCarImportTax-apk`** artifact on each run under the **Actions** tab if you
prefer (it downloads as a zip you then extract).

The app has two tabs: a **Calculator** and a **Guide** that explains every input
field, how Lebanese car import tax works, and the green-vehicle incentives.

## What it calculates

- Customs duty (default 5%)
- Excise / consumption tax (default 45%)
- VAT (default 11%, applied on value + duties)
- Optional 3% additional customs fee (toggle, off by default)
- **Vehicle type (petrol/diesel, hybrid, electric)** applying the 2024 budget-law
  green-vehicle relief: hybrids get customs + excise −80% and registration −70%;
  fully electric cars are exempt from customs + excise and get registration −70%
  (VAT still applies to both)
- Optional CIF basis (folds shipping + insurance into the customs base)
- Shipping, marine insurance, broker / clearance, port handling, registration + plates
- Import cost (everything on top of the car) and the all-in landed total
- Lebanese pound equivalents at an editable exchange rate

Every rate and fee is an editable field, so the same app handles any vehicle, not just
the worked example. It opens pre-filled with the 2021 Porsche Macan Turbo case
(value 48,600), which produces roughly 32,300 in duties and VAT and about 85,600 landed.

The standard 5% customs + 45% excise + 11% VAT structure and the electric/hybrid relief
are based on Lebanon's official customs calculator (customs.gov.lb) and the 2024 budget
law (Article 69). Figures are estimates — confirm with a licensed broker before importing.

## Requirements

- Android Studio (Ladybug 2024.2 or newer recommended)
- JDK 17 (bundled with current Android Studio)
- An emulator or a device running Android 8.0 (API 26) or higher

## Build and run

1. Open Android Studio, choose **Open**, and select this `LebaneseCarImportTax` folder.
2. Let Gradle sync. Android Studio will provision the Gradle wrapper and download
   dependencies automatically the first time. Accept any prompt to update the Android
   Gradle Plugin if your Studio version is newer than the one pinned here.
3. Press **Run** to install on a connected device or emulator, or use
   **Build > Build App Bundle(s) / APK(s) > Build APK(s)** to produce an installable APK.
   The debug APK lands in `app/build/outputs/apk/debug/`.

### Command line (optional)

The Gradle wrapper is committed, so you only need a JDK 17 and the Android SDK:

```
./gradlew assembleDebug  # builds app/build/outputs/apk/debug/app-debug.apk
```

## Project layout

```
app/src/main/java/com/bassem/carimporttax/
  CalculatorLogic.kt   pure calculation (inputs -> result), no Android dependencies
  MainActivity.kt      Compose UI, live recalculation
  ui/theme/            Material 3 theme, cedar-red accent
app/src/main/res/      strings, colors, themes, adaptive launcher icon
```

The calculation is isolated in `CalculatorLogic.kt`, so it is easy to unit test or reuse.

## Notes on the numbers

Lebanese customs values used cars on published Blue Book / Schwacke figures rather than
the invoice, which is why the app takes that value as the customs basis. The headline
"effective tax" is duties + VAT as a percentage of the vehicle value (about 66.5% with
the default rates). The 3% additional customs fee has been re-extended in successive
budget laws, so its status depends on the law in force. These are estimates; confirm the
exact figure with a licensed broker or the official calculator at customs.gov.lb.

## Building without a desktop IDE

The project includes two ways to produce an APK without opening Android Studio:

### Cloud build (phone only) — `.github/workflows/build.yml`
Pushing to this repo runs the **Build APK** workflow automatically. It compiles the app
with the committed Gradle wrapper and then:

- attaches **`LebaneseCarImportTax.apk`** to the rolling **`apk-latest`** GitHub Release
  (a direct, tappable download you can install from your phone), and
- uploads the same file as the **`LebaneseCarImportTax-apk`** artifact under the run on
  the **Actions** tab (downloads as a zip you extract first).

The first time you install, enable "install unknown apps" for your browser or file
manager, then tap the APK again.

### Home server / any Linux box — `Dockerfile`
```
DOCKER_BUILDKIT=1 docker build --target export --output ./out .
```
This drops `out/app-debug.apk` on the host. Copy it to your phone and tap to install.
The build downloads the Android SDK and Gradle inside the container, so the machine
just needs internet and Docker.

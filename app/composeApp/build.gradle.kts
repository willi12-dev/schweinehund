import org.jetbrains.kotlin.gradle.dsl.JvmTarget

plugins {
    alias(libs.plugins.kotlinMultiplatform)
    alias(libs.plugins.androidApplication)
    alias(libs.plugins.composeMultiplatform)
    alias(libs.plugins.composeCompiler)
}

// Eine Versionsnummer für Server und App: die Datei VERSION im Repo.
val appVersion = rootProject.file("../VERSION").readText().trim()
// Adresse des Servers – GitHub Actions setzt sie mit -PserverUrl=…; lokal der Emulator-Rechner.
val serverUrl = (findProperty("serverUrl") as String?)?.takeIf { it.isNotBlank() } ?: "http://10.0.2.2:5000"

kotlin {
    androidTarget {
        compilerOptions {
            jvmTarget.set(JvmTarget.JVM_17)
        }
    }
    // iOS folgt später (REQ-012) – gemeinsamer Code liegt schon in commonMain.

    sourceSets {
        commonMain.dependencies {
            implementation(compose.runtime)
            implementation(compose.foundation)
            implementation(compose.material3)
            implementation(compose.ui)
            implementation(libs.ktor.client.core)
            implementation(libs.kotlinx.coroutines.core)
            implementation(libs.kotlinx.serialization.json)
        }
        androidMain.dependencies {
            implementation(libs.androidx.activity.compose)
            implementation(libs.ktor.client.okhttp)
            implementation(libs.kotlinx.coroutines.android)
            implementation(project.dependencies.platform(libs.firebase.bom))
            implementation(libs.firebase.messaging)
            implementation(libs.health.connect)
            implementation(libs.mlkit.text)
        }
        commonTest.dependencies {
            implementation(kotlin("test"))
        }
    }
}

android {
    namespace = "app.schweinehund"
    compileSdk = 35

    defaultConfig {
        applicationId = "app.schweinehund"
        minSdk = 26
        targetSdk = 35
        versionName = appVersion
        versionCode = appVersion.split(".").let { it[0].toInt() * 10000 + it[1].toInt() * 100 + it[2].toInt() }
        buildConfigField("String", "SERVER_URL", "\"$serverUrl\"")
    }
    buildFeatures {
        buildConfig = true
    }
    compileOptions {
        sourceCompatibility = JavaVersion.VERSION_17
        targetCompatibility = JavaVersion.VERSION_17
    }
}

// Push nur, wenn GitHub Actions die Firebase-Konfiguration (Secret FIREBASE_APP_KONFIG) abgelegt hat.
if (file("google-services.json").exists()) {
    apply(plugin = "com.google.gms.google-services")
}

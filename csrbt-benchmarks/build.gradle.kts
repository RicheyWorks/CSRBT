// csrbt-benchmarks — JMH rig (ADR-013's marquee feature; replaces the in-suite
// printed rows once its numbers are trusted — ADR-013 §4). Never published.
// Run: ./gradlew :csrbt-benchmarks:jmh
plugins {
    java
    alias(libs.plugins.jmh)
}

group = "io.github.richeyworks"
version = "0.1.0"

tasks.withType<JavaCompile>().configureEach {
    options.release = 17 // see csrbt-core/build.gradle.kts
}

dependencies {
    jmh(project(":csrbt-core"))
    jmh(project(":csrbt-experimental"))
}

// Hoisted out of the jmh {} block (the extension receiver shadows the catalog chain).
// asProvider(): the catalog has both "jmh" and "jmh-plugin", so the accessor nests.
val jmhVer = libs.versions.jmh.asProvider().get()

jmh {
    jmhVersion = jmhVer
    // Defaults for the whole rig; individual benchmarks override via annotations.
    fork = 1
    warmupIterations = 3
    iterations = 5
    resultFormat = "JSON"
    resultsFile = layout.buildDirectory.file("reports/jmh/results.json")
}

// The jmh plugin doesn't hook the jmh source set into `build`/`check`, so a compile
// break in a benchmark would only surface at the next manual jmh run. Feed it in.
tasks.named("check") { dependsOn(tasks.named("compileJmhJava")) }
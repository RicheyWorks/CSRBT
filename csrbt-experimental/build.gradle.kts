// csrbt-experimental — arena, ecology, viability map, cache evolution (ADR-011/012
// research surface). Depends on core; never the other way. Not published
// (revisit-trigger: an external consumer asks for the arena — ADR-013 §4).
plugins {
    `java-library`
}

group = "io.github.richeyworks"
version = "0.1.0"

tasks.withType<JavaCompile>().configureEach {
    options.release = 17 // see csrbt-core/build.gradle.kts
}

dependencies {
    api(project(":csrbt-core")) // experimental types expose core types (TreeContext, genomes)
    implementation(libs.log4j.api)

    testImplementation(platform(libs.junit.bom))
    testImplementation(libs.junit.jupiter)
    testImplementation(libs.log4j.core)
    testRuntimeOnly(libs.junit.platform.launcher)
}

tasks.test {
    useJUnitPlatform()
}

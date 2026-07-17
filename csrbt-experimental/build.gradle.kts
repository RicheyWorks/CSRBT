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

// The ADR-011/012 replay recorders (demo/visualizer.html's food). Wired here so they are
// runnable post-Ant (their javadocs used to say `ant compile`); log through log4j's built-in
// SimpleLogger so the WARN lines SearchArenaSession promises actually print.
listOf(
    "arenaSession" to "io.github.richeyworks.csrbt.experimental.ArenaSession",
    "searchArenaSession" to "io.github.richeyworks.csrbt.experimental.SearchArenaSession",
).forEach { (taskName, mainCls) ->
    tasks.register<JavaExec>(taskName) {
        group = "verification"
        description = "Record the ${if (taskName == "arenaSession") "controller" else "evolution-machine search"} replay session for demo/visualizer.html."
        mainClass = mainCls
        classpath = sourceSets["main"].runtimeClasspath
        systemProperty("log4j2.loggerContextFactory",
                "org.apache.logging.log4j.simple.SimpleLoggerContextFactory")
        systemProperty("org.apache.logging.log4j.simplelog.level", "WARN")
        systemProperty("org.apache.logging.log4j.simplelog.StatusLogger.level", "OFF")
    }
}

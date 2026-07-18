// csrbt-experimental — arena, ecology, viability map, cache evolution (ADR-011/012
// research surface). Depends on core; never the other way. ADR-013 §4's publication
// trigger FIRED 2026-07-18: Brine consumes the cache-evolution loop, so the module is
// now publishable (local repo today; Central rides csrbt-core's Phase 9 release).
plugins {
    `java-library`
    `maven-publish`
}

group = "io.github.richeyworks"
version = "0.1.0"

java {
    withSourcesJar()
}

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

publishing {
    publications {
        create<MavenPublication>("maven") {
            artifactId = "csrbt-experimental"
            from(components["java"])
            pom {
                name = "CSRBT Experimental"
                description = "CSRBT's research surface: strategy arena, ecology, viability map, and cache evolution."
                url = "https://github.com/RicheyWorks/CSRBT"
                licenses {
                    license {
                        name = "MIT License"
                        url = "https://opensource.org/licenses/MIT"
                    }
                }
                developers {
                    developer {
                        id = "RicheyWorks"
                        name = "Richmond"
                    }
                }
                scm {
                    url = "https://github.com/RicheyWorks/CSRBT"
                    connection = "scm:git:https://github.com/RicheyWorks/CSRBT.git"
                }
            }
        }
    }
}

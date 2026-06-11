// csrbt-core — the library. The only published module (ADR-013 §3).
plugins {
    `java-library`
    jacoco
    `maven-publish`
}

// Package relocation (core.* -> io.github.richeyworks.csrbt.*) is held until the
// first Central release dry-run — ADR-013 §3.
group = "io.github.richeyworks"
version = "0.1.0-SNAPSHOT"

java {
    withSourcesJar()
    withJavadocJar()
}

// Same guarantee the Ant build made (release="17"): 17-target bytecode from whatever
// JDK runs Gradle (Gradle 9 itself requires 17+). No toolchain pin — it would force
// auto-provisioning plumbing for contributors whose default JDK is newer.
tasks.withType<JavaCompile>().configureEach {
    options.release = 17
}

dependencies {
    // The library logs through the API only; the implementation is the consumer's choice.
    implementation(libs.log4j.api)

    testImplementation(platform(libs.junit.bom))
    testImplementation(libs.junit.jupiter)
    testImplementation(libs.jqwik) // G2: property tests with shrinking
    // Tests read engine log lines and raise levels via log4j-core's Configurator
    // (see CLAUDE.md "Logging in tests"), so core is a *test* dependency only.
    testImplementation(libs.log4j.core)
    testRuntimeOnly(libs.junit.platform.launcher)
}

tasks.test {
    useJUnitPlatform() // picks up both the Jupiter and jqwik engines
    finalizedBy(tasks.jacocoTestReport)
}

tasks.jacocoTestReport {
    dependsOn(tasks.test)
    reports {
        xml.required = true // badge / CI input
        html.required = true
    }
}

tasks.javadoc {
    (options as StandardJavadocDocletOptions).apply {
        encoding = "UTF-8"
        addStringOption("Xdoclint:none", "-quiet") // tighten once the public API javadoc is curated
    }
}

publishing {
    publications {
        create<MavenPublication>("maven") {
            artifactId = "csrbt-core"
            from(components["java"])
            pom {
                name = "CSRBT"
                description = "A Java ordered-set engine with pluggable, runtime-morphing balancing strategies."
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
    // Signing + Central portal credentials are held until the first release — ADR-013 §3.
}

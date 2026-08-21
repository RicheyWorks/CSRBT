// csrbt-core — the library. The only published module (ADR-013 §3).
plugins {
    `java-library`
    jacoco
    `maven-publish`
    signing
}

// Package relocation (core.* -> io.github.richeyworks.csrbt.*) — ADR-013 §3's held
// trigger, fired 2026-06-11 for the v0.1.0 release.
group = "io.github.richeyworks"
version = "0.3.1"

java {
    withSourcesJar()
    withJavadocJar()
}

// Same guarantee the Ant build made (release="17"): 17-target bytecode from whatever
// JDK runs Gradle (Gradle 9 itself requires 17+). No toolchain pin — it would force
// auto-provisioning plumbing for contributors whose default JDK is newer.
tasks.withType<JavaCompile>().configureEach {
    options.release = 17
    // Sources are UTF-8 (box drawing, arrows, J', H' live in comments AND in string
    // literals). javac's default source encoding is the platform default charset, which
    // is UTF-8 only from JDK 18 on (JEP 400) — on the JDK 17 this build still supports,
    // a windows-1252 host decodes "→" as "â†’" and bakes that into the constants. Pinning
    // it makes compiled behaviour identical on every host. The javadoc tasks already pin
    // theirs; -docencoding follows -encoding, so the generated HTML is UTF-8 too.
    options.encoding = "UTF-8"
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
    // Signing + Central portal credentials are held until the Central release — ADR-013 §3.
}

// Phase 9 release prep: PGP signing + a local staging layout for the Central Portal bundle.
// Signing activates ONLY when SIGNING_KEY is present in the environment, so everyday local
// builds stay signature-free. Stage with: ./gradlew publishMavenPublicationToStagingRepository
publishing {
    repositories {
        maven {
            name = "staging"
            url = uri(layout.buildDirectory.dir("staging-deploy"))
        }
    }
}

signing {
    val key = providers.environmentVariable("SIGNING_KEY").orNull
    val pass = providers.environmentVariable("SIGNING_PASSWORD").orNull
    isRequired = key != null
    if (key != null) {
        useInMemoryPgpKeys(key, pass)
        sign(publishing.publications["maven"])
    }
}

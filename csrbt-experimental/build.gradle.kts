// csrbt-experimental — arena, ecology, viability map, cache evolution (ADR-011/012
// research surface). Depends on core; never the other way. ADR-013 §4's publication
// trigger FIRED 2026-07-18: Brine consumes the cache-evolution loop, so the module is
// now publishable (local repo today; Central rides csrbt-core's Phase 9 release).
plugins {
    `java-library`
    `maven-publish`
    signing
}

group = "io.github.richeyworks"
version = "0.2.0"

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

// ADR-016 polish: the ecology field-day demo — narrated plain-English report on stdout
// plus docs/ecology-lab-session.json for docs/ecology-lab.html. Deterministic (seeded).
tasks.register<JavaExec>("ecologyFieldDay") {
    group = "verification"
    description = "Run the ecology field day: narrated report + docs/ecology-lab-session.json."
    mainClass = "io.github.richeyworks.csrbt.experimental.ecology.EcologyFieldDay"
    classpath = sourceSets["main"].runtimeClasspath
    workingDir = rootDir
    systemProperty("log4j2.loggerContextFactory",
            "org.apache.logging.log4j.simple.SimpleLoggerContextFactory")
    systemProperty("org.apache.logging.log4j.simplelog.level", "WARN")
    systemProperty("org.apache.logging.log4j.simplelog.StatusLogger.level", "OFF")
}

// Your workload as an ecosystem: replay a CSV op trace through the instruments.
// ./gradlew ecologyTrace -Ptrace=path/to/trace.csv   (default: docs/sample-trace.csv)
tasks.register<JavaExec>("ecologyTrace") {
    group = "verification"
    description = "Replay an op trace (op,key CSV) through the ecology instruments."
    mainClass = "io.github.richeyworks.csrbt.experimental.ecology.WorkloadTrace"
    classpath = sourceSets["main"].runtimeClasspath
    workingDir = rootDir
    args((project.findProperty("trace") as String?) ?: "docs/sample-trace.csv")
    systemProperty("log4j2.loggerContextFactory",
            "org.apache.logging.log4j.simple.SimpleLoggerContextFactory")
    systemProperty("org.apache.logging.log4j.simplelog.level", "WARN")
    systemProperty("org.apache.logging.log4j.simplelog.StatusLogger.level", "OFF")
}

// The classroom seam (ADR-019): run a plain-text experiment spec.
// ./gradlew ecologyExperiment -Pspec=path/to/experiment.eco   (default: docs/sample-experiment.eco)
tasks.register<JavaExec>("ecologyExperiment") {
    group = "verification"
    description = "Run a classroom experiment spec (.eco): phases, models, crosses, graded hypotheses."
    mainClass = "io.github.richeyworks.csrbt.experimental.ecology.ExperimentLab"
    classpath = sourceSets["main"].runtimeClasspath
    workingDir = rootDir
    args((project.findProperty("spec") as String?) ?: "docs/sample-experiment.eco")
    systemProperty("log4j2.loggerContextFactory",
            "org.apache.logging.log4j.simple.SimpleLoggerContextFactory")
    systemProperty("org.apache.logging.log4j.simplelog.level", "WARN")
    systemProperty("org.apache.logging.log4j.simplelog.StatusLogger.level", "OFF")
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

// Phase 9 release prep: Central requires a javadoc jar per artifact.
java {
    withJavadocJar()
}

tasks.javadoc {
    (options as StandardJavadocDocletOptions).apply {
        encoding = "UTF-8"
        addStringOption("Xdoclint:none", "-quiet")
    }
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

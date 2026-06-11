// ADR-013: Gradle multi-module build. Modules encode the dependency direction
// that was previously only documented: experimental -> core, benchmarks -> both.
rootProject.name = "csrbt"

include("csrbt-core", "csrbt-experimental", "csrbt-benchmarks")

dependencyResolutionManagement {
    repositoriesMode = RepositoriesMode.FAIL_ON_PROJECT_REPOS
    repositories {
        mavenCentral()
    }
}

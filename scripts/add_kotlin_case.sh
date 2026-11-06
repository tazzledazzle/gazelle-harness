#!/usr/bin/env bash
# Creates the Kotlin golden cases. Expectations are generated afterwards with --update.
set -e
cd "$(git rev-parse --show-toplevel)"
K=golden/cases/kotlin
for c in crosspkg samepkg tests mixed plugin; do
  mkdir -p "$K/$c/input"
  echo '-lang=kotlin' > "$K/$c/arguments.txt"
done

# 1. crosspkg: an import of a top-level function in another directory
mkdir -p $K/crosspkg/input/lib $K/crosspkg/input/app
cat > $K/crosspkg/input/lib/Util.kt <<'EOF'
package com.example.lib

fun shout(text: String): String = text.uppercase() + "!"

class Box(val value: String)
EOF
cat > $K/crosspkg/input/app/App.kt <<'EOF'
package com.example.app

import com.example.lib.shout

fun main() {
    println(shout("hi"))
}
EOF

# 2. samepkg: file mode, one file uses another's class with no import
mkdir -p $K/samepkg/input/p
cat > $K/samepkg/input/BUILD.in <<'EOF'
# gazelle:kt_generation_mode file
EOF
cat > $K/samepkg/input/p/A.kt <<'EOF'
package x.p

class A
EOF
cat > $K/samepkg/input/p/B.kt <<'EOF'
package x.p

fun useA() = A()
EOF

# 3. tests: Maven imports, a test rule, and associates
mkdir -p $K/tests/input/svc
cat > $K/tests/input/BUILD.in <<'EOF'
# gazelle:kt_maven_install_file maven_install.json
EOF
cat > $K/tests/input/maven_install.json <<'EOF'
{"version": "2", "artifacts": {}, "dependencies": {}, "packages": {
  "org.jetbrains.kotlinx:kotlinx-coroutines-core": ["kotlinx.coroutines"],
  "org.junit.jupiter:junit-jupiter-api": ["org.junit.jupiter.api"]}}
EOF
cat > $K/tests/input/svc/Api.kt <<'EOF'
package com.example.svc

import kotlinx.coroutines.launch

fun api() = 1
EOF
cat > $K/tests/input/svc/ApiTest.kt <<'EOF'
package com.example.svc

import org.junit.jupiter.api.Test

class ApiTest {
    @Test fun works() { api() }
}
EOF

# 4. mixed: a Java file next to a Kotlin file
mkdir -p $K/mixed/input/m
cat > $K/mixed/input/m/Api.kt <<'EOF'
package com.example.m

fun api() = 1
EOF
cat > $K/mixed/input/m/Legacy.java <<'EOF'
package com.example.m;

public class Legacy {}
EOF

# 5. plugin: a compiler plugin attached by import prefix
mkdir -p $K/plugin/input/model
cat > $K/plugin/input/BUILD.in <<'EOF'
# gazelle:kt_plugin kotlinx.serialization //tools:serialization_plugin
EOF
cat > $K/plugin/input/model/Model.kt <<'EOF'
package com.example.model

import kotlinx.serialization.Serializable

@Serializable
class Model(val x: Int)
EOF
echo "created cases under $K"
#!/usr/bin/env python3
"""
Ripulisce bundle_fixup/CMakeLists.txt:
1. Rimuove le righe orfane (residuo di un sed precedente fallito)
   subito dopo la chiusura del primo blocco install(DIRECTORY ...).
2. Inserisce un blocco pulito install(CODE ...) che risolve la catena
   di symlink dei plugin imageformats (libqgif/libqico/libqjpeg/libqsvg),
   copiando il file reale invece del link relativo rotto.

Uso: python3 fix_bundle_fixup.py bundle_fixup/CMakeLists.txt
"""
import sys

path = sys.argv[1]
with open(path, 'r') as f:
    lines = f.readlines()

target_idx = None
for i, line in enumerate(lines):
    if 'PATTERN "*${CMAKE_SHARED_LIBRARY_SUFFIX}.dSYM" EXCLUDE' in line:
        target_idx = i
        break

if target_idx is None:
    print("ERRORE: non trovato il marker atteso. Nessuna modifica effettuata.")
    sys.exit(1)

close_idx = target_idx + 1
if lines[close_idx].strip() != ')':
    print(f"ERRORE: riga {close_idx+1} non è ')' come atteso (è: {lines[close_idx]!r}). Nessuna modifica effettuata.")
    sys.exit(1)

i = close_idx + 1
while i < len(lines) and lines[i].strip() != 'install (':
    i += 1

if i >= len(lines):
    print("ERRORE: non trovato il blocco 'install (' successivo. Nessuna modifica effettuata.")
    sys.exit(1)

orphan_start = close_idx + 1
orphan_end = i

removed = lines[orphan_start:orphan_end]
print(f"Rimuovo {len(removed)} righe orfane (righe {orphan_start+1}-{orphan_end}):")
for r in removed:
    print("  -", r.rstrip())

new_block = '''    install (CODE "
      file (COPY
        \\"${QT_PLUGINS_DIR}/imageformats/libqgif.dylib\\"
        \\"${QT_PLUGINS_DIR}/imageformats/libqico.dylib\\"
        \\"${QT_PLUGINS_DIR}/imageformats/libqjpeg.dylib\\"
        \\"${QT_PLUGINS_DIR}/imageformats/libqsvg.dylib\\"
        DESTINATION \\"\\${CMAKE_INSTALL_PREFIX}/${WSJT_PLUGIN_DESTINATION}/imageformats\\"
        FOLLOW_SYMLINK_CHAIN
        )"
      CONFIGURATIONS Release MinSizeRel RelWithDebInfo
      )
'''

new_lines = lines[:orphan_start] + [new_block] + lines[orphan_end:]

with open(path, 'w') as f:
    f.writelines(new_lines)

print(f"\nFatto. Blocco pulito inserito subito dopo la riga {close_idx+1}.")

#!/usr/bin/env python3
"""
Sostituisce l'intero blocco di installazione plugin per APPLE
(dal commento "# install required Qt plugins" fino alla chiusura
dell'install(FILES ... libqsqlite ...)) con un unico blocco
install(CODE ...) basato su file(COPY ... FOLLOW_SYMLINK_CHAIN ...),
che risolve la catena di symlink Homebrew per TUTTI i plugin
(platforms, audio, accessible, imageformats, styles, sqldrivers)
in un colpo solo, invece di gestirli uno a uno.

Uso: python3 fix_bundle_fixup_v2.py bundle_fixup/CMakeLists.txt
"""
import sys

path = sys.argv[1]
with open(path, 'r') as f:
    lines = f.readlines()

start_idx = None
for i, line in enumerate(lines):
    if '# install required Qt plugins' in line:
        start_idx = i
        break

if start_idx is None:
    print("ERRORE: marker di inizio non trovato.")
    sys.exit(1)

sqldriver_line_idx = None
for i in range(start_idx, len(lines)):
    if 'libqsqlite${CMAKE_SHARED_LIBRARY_SUFFIX}' in lines[i]:
        sqldriver_line_idx = i
        break

if sqldriver_line_idx is None:
    print("ERRORE: marker sqldrivers (libqsqlite) non trovato dopo l'inizio.")
    sys.exit(1)

end_idx = None
for i in range(sqldriver_line_idx, len(lines)):
    if lines[i].strip() == ')':
        end_idx = i
        break

if end_idx is None:
    print("ERRORE: chiusura ')' del blocco sqldrivers non trovata.")
    sys.exit(1)

removed = lines[start_idx:end_idx + 1]
print(f"Sostituisco {len(removed)} righe (righe {start_idx+1}-{end_idx+1}) con il blocco unificato.")
print("Prime 3 righe rimosse:")
for r in removed[:3]:
    print("  -", r.rstrip())
print("Ultime 3 righe rimosse:")
for r in removed[-3:]:
    print("  -", r.rstrip())

new_block = '''    # install required Qt plugins (usa file(COPY ... FOLLOW_SYMLINK_CHAIN)
    # invece di install(DIRECTORY/FILES) perche' i plugin di Homebrew sono
    # symlink relativi che install() copia cosi' come sono, risultando in
    # link rotti una volta spostati dentro il bundle)
    install (CODE "
      file (COPY
        \\"${QT_PLUGINS_DIR}/platforms\\"
        \\"${QT_PLUGINS_DIR}/audio\\"
        \\"${QT_PLUGINS_DIR}/accessible\\"
        \\"${QT_PLUGINS_DIR}/imageformats\\"
        \\"${QT_PLUGINS_DIR}/styles\\"
        DESTINATION \\"\\${CMAKE_INSTALL_PREFIX}/${WSJT_PLUGIN_DESTINATION}\\"
        FOLLOW_SYMLINK_CHAIN
        FILES_MATCHING PATTERN \\"*${CMAKE_SHARED_LIBRARY_SUFFIX}\\"
        PATTERN \\"*minimal*${CMAKE_SHARED_LIBRARY_SUFFIX}\\" EXCLUDE
        PATTERN \\"*offscreen*${CMAKE_SHARED_LIBRARY_SUFFIX}\\" EXCLUDE
        PATTERN \\"*quick*${CMAKE_SHARED_LIBRARY_SUFFIX}\\" EXCLUDE
        PATTERN \\"*webgl*${CMAKE_SHARED_LIBRARY_SUFFIX}\\" EXCLUDE
        PATTERN \\"*_debug${CMAKE_SHARED_LIBRARY_SUFFIX}\\" EXCLUDE
        PATTERN \\"*${CMAKE_SHARED_LIBRARY_SUFFIX}.dSYM\\" EXCLUDE
        )
      file (COPY
        \\"${QT_PLUGINS_DIR}/sqldrivers/libqsqlite${CMAKE_SHARED_LIBRARY_SUFFIX}\\"
        DESTINATION \\"\\${CMAKE_INSTALL_PREFIX}/${WSJT_PLUGIN_DESTINATION}/sqldrivers\\"
        FOLLOW_SYMLINK_CHAIN
        )"
      CONFIGURATIONS Release MinSizeRel RelWithDebInfo
      )
'''

new_lines = lines[:start_idx] + [new_block] + lines[end_idx + 1:]

with open(path, 'w') as f:
    f.writelines(new_lines)

print(f"\nFatto. Blocco unificato scritto al posto delle righe {start_idx+1}-{end_idx+1}.")

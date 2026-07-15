#!/bin/bash
# Porting CMakeLists.txt di wsjt-z da Qt5 a Qt6
# Lanciare dalla cartella radice del repo wsjt-z (dove sta CMakeLists.txt)

set -e

FILE="CMakeLists.txt"

if [ ! -f "$FILE" ]; then
  echo "Errore: $FILE non trovato in questa cartella. Esegui lo script dalla root di wsjt-z."
  exit 1
fi

# backup
cp "$FILE" "${FILE}.bak-qt5"
echo "Backup salvato in ${FILE}.bak-qt5"

# macOS usa BSD sed: serve l'estensione di backup vuota '' dopo -i
SED_INPLACE=(-i '')

# 1. find_package Qt5 -> Qt6 (componenti principali)
sed "${SED_INPLACE[@]}" \
  -e 's/find_package (Qt5 COMPONENTS Widgets SerialPort Multimedia PrintSupport Sql LinguistTools WebSockets REQUIRED)/find_package (Qt6 COMPONENTS Widgets SerialPort Multimedia PrintSupport Sql LinguistTools WebSockets REQUIRED)/' \
  "$FILE"

# 2. Qt5AxContainer -> Qt6 AxContainer + AxServer (Windows)
sed "${SED_INPLACE[@]}" \
  -e 's/find_package (Qt5AxContainer REQUIRED)/find_package (Qt6 REQUIRED COMPONENTS AxContainer AxServer)/' \
  "$FILE"

# 3. get_target_property Qt5::qmake / Qt5::lconvert -> Qt6
sed "${SED_INPLACE[@]}" \
  -e 's/Qt5::qmake/Qt6::qmake/' \
  -e 's/Qt5::lconvert/Qt6::lconvert/' \
  "$FILE"

# 4. target_link_libraries: Qt5:: -> Qt6:: (sostituzione globale)
#    gestita PRIMA del caso speciale AxBase, così AxBase non viene
#    lasciato come Qt6::AxBase per errore
sed "${SED_INPLACE[@]}" \
  -e 's/Qt5::AxBase/Qt6::AxServer/g' \
  -e 's/Qt5::/Qt6::/g' \
  "$FILE"

# 5. Aggiungi lo standard C++17, richiesto da Qt6.
#    Lo inseriamo subito dopo la riga find_package (Qt6 COMPONENTS ... REQUIRED)
#    solo se non è già presente nel file.
if ! grep -q "CMAKE_CXX_STANDARD 17" "$FILE"; then
  sed "${SED_INPLACE[@]}" \
    -e '/find_package (Qt6 COMPONENTS Widgets SerialPort Multimedia PrintSupport Sql LinguistTools WebSockets REQUIRED)/a\
\
set (CMAKE_CXX_STANDARD 17)\
set (CMAKE_CXX_STANDARD_REQUIRED ON)
' \
    "$FILE"
  echo "Aggiunto CMAKE_CXX_STANDARD 17"
else
  echo "CMAKE_CXX_STANDARD 17 già presente, non modificato"
fi

echo ""
echo "Fatto. Verifica il risultato con:"
echo "  diff ${FILE}.bak-qt5 ${FILE}"
echo ""
echo "Poi ripulisci la build precedente e riconfigura con Qt6, ad es.:"
echo "  rm -rf build && mkdir build && cd build"
echo "  cmake -DCMAKE_PREFIX_PATH=\"/opt/homebrew/opt/qt6;/opt/homebrew/opt/hamlib-471\" .."
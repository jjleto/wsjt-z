#!/bin/bash
# Porting Audio/BWFFile.cpp da Qt5 a Qt6 (QAudioFormat non ha piu'
# setByteOrder/byteOrder, setCodec/codec, setSampleSize, setSampleType)
#
# Lanciare dalla root del repo wsjt-z

set -e

FILE="Audio/BWFFile.cpp"

if [ ! -f "$FILE" ]; then
  echo "Errore: $FILE non trovato. Esegui dalla root di wsjt-z."
  exit 1
fi

cp "$FILE" "${FILE}.bak-qt5"
echo "Backup salvato in ${FILE}.bak-qt5"

SED_INPLACE=(-i '')

# 1. Aggiungi i due nuovi membri subito dopo "QAudioFormat format_;"
#    (in-class default member initializer, non serve toccare i 3 costruttori)
sed "${SED_INPLACE[@]}" \
  -e '/^  QAudioFormat format_;$/a\
  bool big_endian_ {false};       // Qt6: QAudioFormat non ha piu byteOrder\
  int bits_per_sample_ {16};      // Qt6: QAudioFormat non ha piu sampleSize
' \
  "$FILE"

# 2. read_header(): sostituisci setByteOrder -> memorizza in big_endian_
sed "${SED_INPLACE[@]}" \
  -e 's/format_\.setByteOrder (be ? QAudioFormat::BigEndian : QAudioFormat::LittleEndian);/big_endian_ = be;/' \
  "$FILE"

# 3. read_header(): rimuovi setCodec (Qt6 assume sempre PCM)
sed "${SED_INPLACE[@]}" \
  -e '/format_\.setCodec ("audio\/pcm");/d' \
  "$FILE"

# 4. read_header(): setSampleSize + setSampleType -> setSampleFormat, e traccia bits_per_sample_
sed "${SED_INPLACE[@]}" \
  -e 's/format_\.setSampleSize (bits_per_sample);/bits_per_sample_ = bits_per_sample;/' \
  -e 's/format_\.setSampleType (8 == bits_per_sample ? QAudioFormat::UnSignedInt : QAudioFormat::SignedInt);/format_.setSampleFormat (8 == bits_per_sample ? QAudioFormat::UInt8 : 32 == bits_per_sample ? QAudioFormat::Int32 : QAudioFormat::Int16);/' \
  "$FILE"

# 5. write_header(): rimuovi il controllo sul codec (Qt6 assume sempre PCM)
sed "${SED_INPLACE[@]}" \
  -e '/if ("audio\/pcm" != format\.codec ()) return false;/d' \
  "$FILE"

# 6. write_header() e update_header(): bool be {...byteOrder...} -> usa big_endian_
sed "${SED_INPLACE[@]}" \
  -e 's/bool be {QAudioFormat::BigEndian == format_\.byteOrder ()};/bool be {big_endian_};/g' \
  "$FILE"

# 7. write_header(): format.sampleSize() -> format.bytesPerSample () * 8
sed "${SED_INPLACE[@]}" \
  -e 's/format\.sampleSize ()/format.bytesPerSample () * 8/g' \
  "$FILE"

echo ""
echo "Fatto. Verifica il risultato con:"
echo "  diff ${FILE}.bak-qt5 ${FILE}"
echo ""
echo "Controlla anche a mano se restano altri usi di:"
echo "  format_.codec() / format_.sampleSize() / format_.byteOrder()"
echo "altrove nel file (es. in punti non coperti dal grep iniziale):"
echo "  grep -n 'codec\\|sampleSize\\|byteOrder\\|SampleType\\|UnSignedInt' ${FILE}"
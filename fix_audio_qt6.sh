#!/bin/bash
# Migrazione sottosistema audio Qt5 -> Qt6:
#   QAudioDeviceInfo -> QAudioDevice
#   QAudioInput      -> QAudioSource
#   QAudioOutput     -> QAudioSink
#
# Lanciare dalla root del repo wsjt-z

set -e
SED_INPLACE=(-i '')

backup() {
  cp "$1" "$1.bak-qt5"
}

# ========== Audio/soundin.h ==========
F="Audio/soundin.h"
backup "$F"
sed "${SED_INPLACE[@]}" \
  -e 's/#include <QAudioInput>/#include <QAudioSource>/' \
  -e 's/class QAudioDeviceInfo;/class QAudioDevice;/' \
  -e 's/class QAudioInput;/class QAudioSource;/' \
  -e 's/QAudioDeviceInfo const&, int framesPerBuffer/QAudioDevice const\&, int framesPerBuffer/' \
  -e 's/QScopedPointer<QAudioInput> m_stream;/QScopedPointer<QAudioSource> m_stream;/' \
  "$F"

# ========== Audio/soundin.cpp ==========
F="Audio/soundin.cpp"
backup "$F"
sed "${SED_INPLACE[@]}" \
  -e 's/#include <QAudioDeviceInfo>/#include <QAudioDevice>/' \
  -e 's/#include <QAudioInput>/#include <QAudioSource>/' \
  -e 's/void SoundInput::start(QAudioDeviceInfo const& device/void SoundInput::start(QAudioDevice const\& device/' \
  -e '/format.setCodec ("audio\/pcm");/d' \
  -e 's/format.setSampleSize (16);/format.setSampleFormat (QAudioFormat::Int16);/' \
  -e '/format.setByteOrder (QAudioFormat::Endian (QSysInfo::ByteOrder));/d' \
  -e 's/m_stream.reset (new QAudioInput {device, format});/m_stream.reset (new QAudioSource {device, format});/' \
  -e 's/&QAudioInput::stateChanged/\&QAudioSource::stateChanged/' \
  -e 's/&QAudioInput::notify/\&QAudioSource::notify/' \
  "$F"
# rimuovi separatamente la riga setSampleType (piu' affidabile come passata isolata)
sed "${SED_INPLACE[@]}" -e '/format.setSampleType (QAudioFormat::SignedInt);/d' "$F"

# ========== Audio/soundout.h ==========
F="Audio/soundout.h"
backup "$F"
sed "${SED_INPLACE[@]}" \
  -e 's/#include <QAudioOutput>/#include <QAudioSink>/' \
  -e 's/#include <QAudioDeviceInfo>/#include <QAudioDevice>/' \
  -e 's/class QAudioDeviceInfo;/class QAudioDevice;/' \
  -e 's/void setFormat (QAudioDeviceInfo const& device/void setFormat (QAudioDevice const\& device/' \
  -e 's/QAudioDeviceInfo m_device;/QAudioDevice m_device;/' \
  -e 's/QScopedPointer<QAudioOutput> m_stream;/QScopedPointer<QAudioSink> m_stream;/' \
  "$F"

# ========== Audio/soundout.cpp ==========
F="Audio/soundout.cpp"
backup "$F"
sed "${SED_INPLACE[@]}" \
  -e 's/#include <QAudioDeviceInfo>/#include <QAudioDevice>/' \
  -e 's/#include <QAudioOutput>/#include <QAudioSink>/' \
  -e 's/void SoundOutput::setFormat (QAudioDeviceInfo const& device/void SoundOutput::setFormat (QAudioDevice const\& device/' \
  -e '/format.setCodec ("audio\/pcm");/d' \
  -e 's/format.setSampleSize (16);/format.setSampleFormat (QAudioFormat::Int16);/' \
  -e '/format.setByteOrder (QAudioFormat::Endian (QSysInfo::ByteOrder));/d' \
  -e 's/m_stream.reset (new QAudioOutput (m_device, format));/m_stream.reset (new QAudioSink (m_device, format));/' \
  -e 's/&QAudioOutput::stateChanged/\&QAudioSink::stateChanged/' \
  -e 's/&QAudioOutput::notify/\&QAudioSink::notify/' \
  "$F"
sed "${SED_INPLACE[@]}" -e '/format.setSampleType (QAudioFormat::SignedInt);/d' "$F"

# ========== Configuration.hpp ==========
F="Configuration.hpp"
backup "$F"
sed "${SED_INPLACE[@]}" \
  -e 's/class QAudioDeviceInfo;/class QAudioDevice;/' \
  -e 's/QAudioDeviceInfo const& audio_input_device/QAudioDevice const\& audio_input_device/' \
  -e 's/QAudioDeviceInfo const& audio_output_device/QAudioDevice const\& audio_output_device/' \
  "$F"

# ========== Configuration.cpp ==========
F="Configuration.cpp"
backup "$F"
sed "${SED_INPLACE[@]}" \
  -e 's/#include <QAudioDeviceInfo>/#include <QAudioDevice>\n#include <QMediaDevices>/' \
  -e 's/#include <QAudioInput>/#include <QAudioSource>/' \
  -e 's/using audio_info_type = QPair<QAudioDeviceInfo, QList<QVariant> >;/using audio_info_type = QPair<QAudioDevice, QList<QVariant> >;/' \
  -e 's/typedef QList<QAudioDeviceInfo> AudioDevices;/typedef QList<QAudioDevice> AudioDevices;/' \
  -e 's/QAudioDeviceInfo find_audio_device/QAudioDevice find_audio_device/' \
  -e 's/void load_audio_devices (QAudio::Mode, QComboBox \*, QAudioDeviceInfo \*);/void load_audio_devices (QAudio::Mode, QComboBox *, QAudioDevice *);/' \
  -e 's/QAudioDeviceInfo audio_input_device_;/QAudioDevice audio_input_device_;/' \
  -e 's/QAudioDeviceInfo next_audio_input_device_;/QAudioDevice next_audio_input_device_;/' \
  -e 's/QAudioDeviceInfo audio_output_device_;/QAudioDevice audio_output_device_;/' \
  -e 's/QAudioDeviceInfo next_audio_output_device_;/QAudioDevice next_audio_output_device_;/' \
  -e 's/QAudioDeviceInfo const& Configuration::audio_input_device/QAudioDevice const\& Configuration::audio_input_device/' \
  -e 's/QAudioDeviceInfo const& Configuration::audio_output_device/QAudioDevice const\& Configuration::audio_output_device/' \
  -e 's/m_->audio_input_device_ = QAudioDeviceInfo {};/m_->audio_input_device_ = QAudioDevice {};/' \
  -e 's/m_->audio_output_device_ = QAudioDeviceInfo {};/m_->audio_output_device_ = QAudioDevice {};/' \
  -e 's/\.deviceName ()/.description ()/g' \
  -e 's/QAudioDeviceInfo Configuration::impl::find_audio_device/QAudioDevice Configuration::impl::find_audio_device/' \
  -e 's/, QAudioDeviceInfo \* device)/, QAudioDevice * device)/' \
  "$F"

# le due chiamate a availableDevices(mode) vanno sostituite con la nuova API
# QMediaDevices, che distingue input/output invece di usare QAudio::Mode
sed "${SED_INPLACE[@]}" \
  -e 's/auto const& devices = QAudioDeviceInfo::availableDevices (mode);/auto const\& devices = (QAudio::AudioInput == mode) ? QMediaDevices::audioInputs () : QMediaDevices::audioOutputs ();/g' \
  Configuration.cpp

echo ""
echo "NOTA: 'm_stream->setCategory (\"production\");' in soundout.cpp potrebbe non"
echo "avere equivalente diretto su QAudioSink in Qt6 (era specifico PulseAudio/Linux)."
echo "Se il prossimo errore di compilazione lo segnala, probabilmente va rimossa quella riga."
echo ""

# ========== widgets/mainwindow.h ==========
F="widgets/mainwindow.h"
backup "$F"
sed "${SED_INPLACE[@]}" \
  -e 's/#include <QAudioDeviceInfo>/#include <QAudioDevice>/' \
  -e 's/Q_SIGNAL void initializeAudioOutputStream (QAudioDeviceInfo,/Q_SIGNAL void initializeAudioOutputStream (QAudioDevice,/' \
  -e 's/Q_SIGNAL void startAudioInputStream (QAudioDeviceInfo const&,/Q_SIGNAL void startAudioInputStream (QAudioDevice const\&,/' \
  "$F"

echo ""
echo "Fatto. Verifica con: diff Configuration.hpp.bak-qt5 Configuration.hpp"
echo "e con: diff Configuration.cpp.bak-qt5 Configuration.cpp"
echo "e con: diff widgets/mainwindow.h.bak-qt5 widgets/mainwindow.h"

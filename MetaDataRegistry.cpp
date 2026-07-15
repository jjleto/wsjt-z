#include "MetaDataRegistry.hpp"

#include <QMetaType>
#include <QItemEditorFactory>
#include <QStandardItemEditorCreator>

#include "Radio.hpp"
#include "models/FrequencyList.hpp"
#include "Audio/AudioDevice.hpp"
#include "Configuration.hpp"
#include "models/StationList.hpp"
#include "Transceiver/Transceiver.hpp"
#include "Transceiver/TransceiverFactory.hpp"
#include "WFPalette.hpp"
#include "models/IARURegions.hpp"
#include "models/DecodeHighlightingModel.hpp"
#include "widgets/DateTimeEdit.hpp"

namespace
{
  class ItemEditorFactory final
    : public QItemEditorFactory
  {
  public:
    ItemEditorFactory ()
      : default_factory_ {QItemEditorFactory::defaultFactory ()}
    {
    }

    QWidget * createEditor (int user_type, QWidget * parent) const override
    {
      auto editor = QItemEditorFactory::createEditor (user_type, parent);
      return editor ? editor : default_factory_->createEditor (user_type, parent);
    }

  private:
    QItemEditorFactory const * default_factory_;
  };
}

void register_types ()
{
  auto item_editor_factory = new ItemEditorFactory;
  QItemEditorFactory::setDefaultFactory (item_editor_factory);

  // types in Radio.hpp are registered in their own translation unit
  // as they are needed in the wsjtx_udp shared library too

  // we still have to register the fully qualified names of enum types
  // used as signal/slot connection arguments since the new Qt 5.5
  // Q_ENUM macro only seems to register the unqualified name
  
  item_editor_factory->registerEditor (qMetaTypeId<QDateTime> (), new QStandardItemEditorCreator<DateTimeEdit> ());

  // V101 Frequency list model
  /* removed for Qt6 */
  QMetaType::registerConverter<FrequencyList_v2_101::Item, QString> (&FrequencyList_v2_101::Item::toString);
  /* removed for Qt6 */

  // V100 Frequency list model
  /* removed for Qt6 */
  /* removed for Qt6 */

  // defunct old versions
  /* removed for Qt6 */
  /* removed for Qt6 */

  // Audio device
  qRegisterMetaType<AudioDevice::Channel> ("AudioDevice::Channel");

  // Configuration
  /* removed for Qt6 */
  /* removed for Qt6 */

  // Station details
  qRegisterMetaType<StationList::Station> ("Station");
  QMetaType::registerConverter<StationList::Station, QString> (&StationList::Station::toString);
  qRegisterMetaType<StationList::Stations> ("Stations");
  /* removed for Qt6 */
  /* removed for Qt6 */

  // Transceiver
  qRegisterMetaType<Transceiver::TransceiverState> ("Transceiver::TransceiverState");

  // Transceiver factory
  /* removed for Qt6 */
  /* removed for Qt6 */
  /* removed for Qt6 */
  /* removed for Qt6 */
  /* removed for Qt6 */
  /* removed for Qt6 */

  // Waterfall palette
  /* removed for Qt6 */

  // IARURegions
  /* removed for Qt6 */

  // DecodeHighlightingModel
  /* removed for Qt6 */
  QMetaType::registerConverter<DecodeHighlightingModel::HighlightInfo, QString> (&DecodeHighlightingModel::HighlightInfo::toString);
  /* removed for Qt6 */
}

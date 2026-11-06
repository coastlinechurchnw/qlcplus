/*
  Q Light Controller Plus - Unit test
  vcbutton_test.cpp

  Copyright (C) Heikki Junnila
                Massimo Callegari

  Licensed under the Apache License, Version 2.0 (the "License");
  you may not use this file except in compliance with the License.
  You may obtain a copy of the License at

      http://www.apache.org/licenses/LICENSE-2.0.txt

  Unless required by applicable law or agreed to in writing, software
  distributed under the License is distributed on an "AS IS" BASIS,
  WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
  See the License for the specific language governing permissions and
  limitations under the License.
*/

#include <QXmlStreamReader>
#include <QXmlStreamWriter>
#include <QObject>
#include <QtTest>
#include <QMenu>

#define protected public
#define private public
#include "qlcfixturedefcache.h"
#include "qlcinputsource.h"
#include "virtualconsole.h"
#include "vcbutton_test.h"
#include "mastertimer.h"
#include "qlcmacros.h"
#include "vcbutton.h"
#include "vcbuttonproperties.h"
#include "vcsoloframe.h"
#include "vcframe.h"
#include "scene.h"
#include "doc.h"
#undef private
#undef protected

static const QKeySequence keySequenceA(Qt::Key_A);
static const QKeySequence keySequenceB(Qt::Key_B);

void VCButton_Test::initTestCase()
{
    m_doc = NULL;
}

void VCButton_Test::init()
{
    m_doc = new Doc(this);
    new VirtualConsole(NULL, m_doc);

    Fixture* fxi = new Fixture(m_doc);
    fxi->setChannels(4);
    m_doc->addFixture(fxi);
}

void VCButton_Test::cleanup()
{
    delete VirtualConsole::instance();
    delete m_doc;
}

void VCButton_Test::initial()
{
    QWidget w;

    VCButton btn(&w, m_doc);
    QCOMPARE(btn.objectName(), QString("VCButton"));
    QCOMPARE(btn.frameStyle(), (int) KVCFrameStyleNone);
    QCOMPARE(btn.caption(), QString());
    QCOMPARE(btn.size(), QSize(50, 50));
    QCOMPARE(btn.function(), Function::invalidId());
    QCOMPARE(btn.startupIntensity(), qreal(1.0));
    QCOMPARE(btn.isStartupIntensityEnabled(), false);
    QCOMPARE(btn.state(), VCButton::Inactive);
    QCOMPARE(btn.action(), VCButton::Toggle);
    QCOMPARE(btn.iconPath(), QString());
    QVERIFY(btn.m_chooseIconAction != NULL);
    QVERIFY(btn.m_resetIconAction != NULL);

    // Only for coverage
    btn.setBackgroundImage(QString());
}

void VCButton_Test::function()
{
    QWidget w;

    VCButton btn(&w, m_doc);
    btn.setFunction(42);
    QCOMPARE(btn.function(), Function::invalidId());

    Scene* s = new Scene(m_doc);
    s->setName("Test1");
    m_doc->addFunction(s);
    btn.setFunction(s->id());
    QCOMPARE(btn.function(), s->id());
    QCOMPARE(btn.toolTip(), QString("Test1"));

    Scene* s2 = new Scene(m_doc);
    s2->setName("Test2");
    m_doc->addFunction(s2);
    btn.setFunction(s2->id());
    QCOMPARE(btn.function(), s2->id());
    QCOMPARE(btn.toolTip(), QString("Test2"));

    btn.setFunction(s2->id() + 1);
    QCOMPARE(btn.function(), Function::invalidId());
    QCOMPARE(btn.toolTip(), QString());

    btn.setFunction(s2->id());
    QCOMPARE(btn.function(), s2->id());
    QCOMPARE(btn.toolTip(), QString("Test2"));

    m_doc->deleteFunction(s2->id());
    QCOMPARE(btn.function(), Function::invalidId());
    QCOMPARE(btn.toolTip(), QString());

    m_doc->deleteFunction(s->id());
    QCOMPARE(btn.function(), Function::invalidId());
    QCOMPARE(btn.toolTip(), QString());
}

void VCButton_Test::action()
{
    QWidget w;

    VCButton btn(&w, m_doc);
    btn.setAction(VCButton::Flash);
    QCOMPARE(btn.action(), VCButton::Flash);
    btn.setAction(VCButton::Toggle);
    QCOMPARE(btn.action(), VCButton::Toggle);

    QCOMPARE(VCButton::actionToString(VCButton::Toggle), QString("Toggle"));
    QCOMPARE(VCButton::actionToString(VCButton::Flash), QString("Flash"));
    QCOMPARE(VCButton::actionToString((VCButton::Action) 31337), QString("Toggle"));
    QCOMPARE(VCButton::stringToAction("Toggle"), VCButton::Toggle);
    QCOMPARE(VCButton::stringToAction("Flash"), VCButton::Flash);
    QCOMPARE(VCButton::stringToAction("Foobar"), VCButton::Toggle);
    QCOMPARE(VCButton::actionToString(VCButton::SetOn), QString("SetOn"));
    QCOMPARE(VCButton::actionToString(VCButton::SetOff), QString("SetOff"));
    QCOMPARE(VCButton::stringToAction("SetOn"), VCButton::SetOn);
    QCOMPARE(VCButton::stringToAction("SetOff"), VCButton::SetOff);
}

void VCButton_Test::intensity()
{
    QWidget w;

    VCButton btn(&w, m_doc);
    btn.enableStartupIntensity(true);
    QCOMPARE(btn.isStartupIntensityEnabled(), true);
    btn.enableStartupIntensity(false);
    QCOMPARE(btn.isStartupIntensityEnabled(), false);

    for (qreal i = -0.5; i < 1.2; i += 0.01)
    {
        btn.setStartupIntensity(i);
        QCOMPARE(btn.startupIntensity(), CLAMP(i, qreal(0.0), qreal(1.0)));
    }
}

void VCButton_Test::bgcolor()
{
    QWidget w;

    VCButton btn(&w, m_doc);
    m_doc->resetModified();
    btn.setBackgroundColor(QColor(Qt::red));
    QCOMPARE(btn.backgroundColor(), QColor(Qt::red));
    QCOMPARE(btn.palette().color(QPalette::Button), QColor(Qt::red));
    QCOMPARE(m_doc->isModified(), true);
    QVERIFY(btn.foregroundColor() != QColor(Qt::red));
}

void VCButton_Test::fgcolor()
{
    QWidget w;

    VCButton btn(&w, m_doc);
    m_doc->resetModified();
    btn.setForegroundColor(QColor(Qt::red));
    QCOMPARE(btn.foregroundColor(), QColor(Qt::red));
    QCOMPARE(btn.palette().color(QPalette::ButtonText), QColor(Qt::red));
    QCOMPARE(btn.palette().color(QPalette::WindowText), QColor(Qt::red));
    QCOMPARE(m_doc->isModified(), true);
    QVERIFY(btn.backgroundColor() != QColor(Qt::red));
}

void VCButton_Test::resetColors()
{
    QWidget w;

    VCButton btn(&w, m_doc);

    btn.setForegroundColor(QColor(Qt::red));
    btn.setBackgroundColor(QColor(Qt::blue));
    m_doc->resetModified();
    btn.resetForegroundColor();
    QCOMPARE(btn.foregroundColor(), w.palette().color(QPalette::WindowText));
    QCOMPARE(btn.backgroundColor(), QColor(Qt::blue));
    QCOMPARE(m_doc->isModified(), true);

    btn.resetForegroundColor();
    QCOMPARE(btn.foregroundColor(), w.palette().color(QPalette::WindowText));
    QCOMPARE(btn.backgroundColor(), QColor(Qt::blue));

    btn.setForegroundColor(QColor(Qt::red));
    btn.setBackgroundColor(QColor(Qt::blue));
    m_doc->resetModified();
    btn.resetBackgroundColor();
    QCOMPARE(btn.backgroundColor(), w.palette().color(QPalette::Button));
    QCOMPARE(btn.foregroundColor(), QColor(Qt::red));
    QCOMPARE(m_doc->isModified(), true);

    btn.resetBackgroundColor();
    QCOMPARE(btn.backgroundColor(), w.palette().color(QPalette::Button));
    QCOMPARE(btn.foregroundColor(), QColor(Qt::red));
}

void VCButton_Test::iconPath()
{
    QWidget w;

    VCButton btn(&w, m_doc);
    m_doc->resetModified();
    btn.setIconPath("../../../resources/icons/png/qlcplus.png");
    QCOMPARE(btn.iconPath(), QString("../../../resources/icons/png/qlcplus.png"));
    QCOMPARE(m_doc->isModified(), true);

    m_doc->resetModified();
    btn.slotResetIcon();
    QCOMPARE(btn.iconPath(), QString());
    QCOMPARE(m_doc->isModified(), true);
}

void VCButton_Test::on()
{
    QWidget w;

    VCButton btn(&w, m_doc);
    btn.setInputSource(QSharedPointer<QLCInputSource>(new QLCInputSource(0, 1)));

    QCOMPARE(btn.state(), VCButton::Inactive);

    btn.setState(VCButton::Inactive);
    QCOMPARE(btn.state(), VCButton::Inactive);

    btn.setState(VCButton::Active);
    QCOMPARE(btn.state(), VCButton::Active);

    btn.setState(VCButton::Active);
    QCOMPARE(btn.state(), VCButton::Active);

    btn.setState(VCButton::Inactive);
    QCOMPARE(btn.state(), VCButton::Inactive);
}

void VCButton_Test::keySequence()
{
    QWidget w;

    VCButton btn(&w, m_doc);
    QCOMPARE(btn.keySequence(), QKeySequence());

    QKeySequence seq(keySequenceA);
    btn.setKeySequence(seq);
    QCOMPARE(btn.keySequence(), seq);

    seq = QKeySequence(keySequenceB);
    QVERIFY(btn.keySequence() != seq);
    btn.setKeySequence(seq);
    QCOMPARE(btn.keySequence(), seq);
}

void VCButton_Test::copy()
{
    QWidget w;

    Scene* sc = new Scene(m_doc);
    m_doc->addFunction(sc);

    VCButton btn(&w, m_doc);
    btn.setCaption("Foobar");
    btn.setIconPath("../../../resources/icons/png/qlcplus.png");
    btn.setFunction(sc->id());
    btn.setAction(VCButton::Flash);
    btn.setKeySequence(QKeySequence(keySequenceB));
    btn.enableStartupIntensity(true);
    btn.setStartupIntensity(qreal(0.2));
    btn.setAction(VCButton::SetOn);

    VCFrame parent(&w, m_doc);
    VCButton* copy = qobject_cast<VCButton*> (btn.createCopy(&parent));
    QVERIFY(copy != NULL);
    QCOMPARE(copy->caption(), QString("Foobar"));
    QCOMPARE(copy->iconPath(), QString("../../../resources/icons/png/qlcplus.png"));
    QCOMPARE(copy->function(), sc->id());
    QCOMPARE(copy->action(), VCButton::SetOn);
    QCOMPARE(copy->keySequence(), QKeySequence(keySequenceB));
    QCOMPARE(copy->isStartupIntensityEnabled(), true);
    QCOMPARE(copy->startupIntensity(), qreal(0.2));
    btn.setAction(VCButton::SetOff);
    QVERIFY(copy->copyFrom(&btn));
    QCOMPARE(copy->action(), VCButton::SetOff);
    delete copy;
}

void VCButton_Test::load()
{
    QWidget w;

    Scene* sc = new Scene(m_doc);
    m_doc->addFunction(sc);
    m_doc->setWorkspacePath(QDir("../../../resources/icons/png").absolutePath());

    QBuffer buffer;
    buffer.open(QIODevice::WriteOnly | QIODevice::Text);
    QXmlStreamWriter xmlWriter(&buffer);

    xmlWriter.writeStartElement("Button");
    xmlWriter.writeAttribute("Caption", "Pertti");
    xmlWriter.writeAttribute("Icon", "qlcplus.png");

    xmlWriter.writeStartElement("WindowState");
    xmlWriter.writeAttribute("X", "20");
    xmlWriter.writeAttribute("Y", "20");
    xmlWriter.writeAttribute("Width", "60");
    xmlWriter.writeAttribute("Height", "60");
    xmlWriter.writeAttribute("Visible", "True");
    xmlWriter.writeEndElement();

    xmlWriter.writeStartElement("Appearance");
    xmlWriter.writeEndElement();

    xmlWriter.writeStartElement("Function");
    xmlWriter.writeAttribute("ID", QString::number(sc->id()));
    xmlWriter.writeEndElement();

    xmlWriter.writeStartElement("Input");
    xmlWriter.writeEndElement();

    xmlWriter.writeTextElement("Action", "Flash");

    xmlWriter.writeTextElement("Key", QKeySequence(keySequenceA).toString());

    xmlWriter.writeStartElement("Intensity");
    xmlWriter.writeAttribute("Adjust", "True");
    xmlWriter.writeCharacters("60");
    xmlWriter.writeEndElement();

    xmlWriter.writeStartElement("Foo");
    xmlWriter.writeEndElement();

    xmlWriter.writeEndDocument();
    xmlWriter.setDevice(NULL);
    buffer.close();

    buffer.open(QIODevice::ReadOnly | QIODevice::Text);
    QXmlStreamReader xmlReader(&buffer);
    xmlReader.readNextStartElement();

    VCButton btn(&w, m_doc);
    QCOMPARE(btn.loadXML(xmlReader), true);
    QCOMPARE(btn.caption(), QString("Pertti"));
    QCOMPARE(btn.iconPath(), QFileInfo(QString("../../../resources/icons/png/qlcplus.png")).canonicalFilePath());
    QCOMPARE(btn.function(), sc->id());
    QCOMPARE(btn.action(), VCButton::Flash);
    QCOMPARE(btn.keySequence(), QKeySequence(keySequenceA));
    QCOMPARE(btn.isStartupIntensityEnabled(), true);
    QCOMPARE(btn.startupIntensity(), qreal(0.6));
    QCOMPARE(btn.pos(), QPoint(20, 20));
    QCOMPARE(btn.size(), QSize(60, 60));

    buffer.close();
    QByteArray bData = buffer.data();
    bData.replace("Adjust=\"True\"", "Adjust=\"False\"");
    buffer.setData(bData);
    buffer.open(QIODevice::ReadOnly | QIODevice::Text);
    buffer.seek(0);
    xmlReader.setDevice(&buffer);
    xmlReader.readNextStartElement();

    QCOMPARE(btn.loadXML(xmlReader), true);
    QCOMPARE(btn.caption(), QString("Pertti"));
    QCOMPARE(btn.iconPath(), QFileInfo(QString("../../../resources/icons/png/qlcplus.png")).canonicalFilePath());
    QCOMPARE(btn.function(), sc->id());
    QCOMPARE(btn.action(), VCButton::Flash);
    QCOMPARE(btn.keySequence(), QKeySequence(keySequenceA));
    QCOMPARE(btn.isStartupIntensityEnabled(), false);
    QCOMPARE(btn.startupIntensity(), qreal(0.6));
    QCOMPARE(btn.pos(), QPoint(20, 20));
    QCOMPARE(btn.size(), QSize(60, 60));

    buffer.close();
    bData = buffer.data();
    bData.replace("<Button", "<Buton");
    buffer.setData(bData);
    buffer.open(QIODevice::ReadOnly | QIODevice::Text);
    buffer.seek(0);
    xmlReader.setDevice(&buffer);
    xmlReader.readNextStartElement();

    QCOMPARE(btn.loadXML(xmlReader), false);
}

void VCButton_Test::save()
{
    QWidget w;

    Scene* sc = new Scene(m_doc);
    m_doc->addFunction(sc);
    m_doc->setWorkspacePath(QDir("../../../resources/icons/png").absolutePath());

    VCButton btn(&w, m_doc);
    btn.setCaption("Foobar");
    btn.setIconPath("../../../resources/icons/png/qlcplus.png");
    btn.setFunction(sc->id());
    btn.setAction(VCButton::Flash);
    btn.setKeySequence(QKeySequence(keySequenceB));
    btn.enableStartupIntensity(true);
    btn.setStartupIntensity(qreal(0.2));
    btn.setFlashForceLTP(true);
    btn.setFlashOverride(true);

    QBuffer buffer;
    buffer.open(QIODevice::WriteOnly | QIODevice::Text);
    QXmlStreamWriter xmlWriter(&buffer);

    int function = 0, action = 0, key = 0, intensity = 0, wstate = 0, appearance = 0, flashProperties = 0;
    QCOMPARE(btn.saveXML(&xmlWriter), true);

    xmlWriter.setDevice(NULL);
    buffer.close();

    buffer.open(QIODevice::ReadOnly | QIODevice::Text);
    QXmlStreamReader xmlReader(&buffer);
    xmlReader.readNextStartElement();

    QCOMPARE(xmlReader.name().toString(), QString("Button"));
    QCOMPARE(xmlReader.attributes().value("Icon").toString(), QString("qlcplus.png"));
    QCOMPARE(xmlReader.attributes().value("Caption").toString(), QString("Foobar"));

    while (xmlReader.readNextStartElement())
    {
        if (xmlReader.name().toString() == "Function")
        {
            function++;
            QCOMPARE(xmlReader.attributes().value("ID").toString(), QString::number(sc->id()));
            xmlReader.skipCurrentElement();
        }
        else if (xmlReader.name().toString() == "Action")
        {
            QCOMPARE(xmlReader.attributes().value("Override").toString(), QString("1"));
            QCOMPARE(xmlReader.attributes().value("ForceLTP").toString(), QString("1"));
            flashProperties++;
            QCOMPARE(xmlReader.readElementText(), QString("Flash"));
            action++;
        }
        else if (xmlReader.name().toString() == "Key")
        {
            key++;
            QCOMPARE(xmlReader.readElementText(), QKeySequence(keySequenceB).toString());
        }
        else if (xmlReader.name().toString() == "Intensity")
        {
            intensity++;
            QCOMPARE(xmlReader.attributes().value("Adjust").toString(), QString("True"));
            QCOMPARE(xmlReader.readElementText(), QString("20"));
        }
        else if (xmlReader.name().toString() == "WindowState")
        {
            wstate++;
            xmlReader.skipCurrentElement();
        }
        else if (xmlReader.name().toString() == "Appearance")
        {
            appearance++;
            xmlReader.skipCurrentElement();
        }
        else
        {
            QFAIL(QString("Unexpected tag: %1").arg(xmlReader.name().toString()).toUtf8().constData());
            xmlReader.skipCurrentElement();
        }
    }

    QCOMPARE(function, 1);
    QCOMPARE(action, 1);
    QCOMPARE(key, 1);
    QCOMPARE(intensity, 1);
    QCOMPARE(wstate, 1);
    QCOMPARE(appearance, 1);
    QCOMPARE(flashProperties, 1);
}

void VCButton_Test::customMenu()
{
    QWidget w;

    VCButton btn(&w, m_doc);
    QMenu* menu = btn.customMenu(NULL);
    QVERIFY(menu != NULL);
    QCOMPARE(menu->title(), tr("Icon"));
    QCOMPARE(menu->actions().size(), 2);
    QCOMPARE(menu->actions()[0], btn.m_chooseIconAction);
    QCOMPARE(menu->actions()[1], btn.m_resetIconAction);
    delete menu;
}

void VCButton_Test::toggle()
{
    QWidget w;

    Scene* sc = new Scene(m_doc);
    sc->setValue(0, 0, 255);
    sc->setFadeInSpeed(1000);
    sc->setFadeOutSpeed(1000);
    m_doc->addFunction(sc);

    VCButton btn(&w, m_doc);
    btn.setCaption("Foobar");
    btn.setFunction(sc->id());
    btn.setAction(VCButton::Toggle);
    btn.setKeySequence(QKeySequence(keySequenceB));
    btn.enableStartupIntensity(true);
    btn.setStartupIntensity(qreal(0.2));

    // Mouse button press in design mode doesn't toggle the function
    QCOMPARE(m_doc->mode(), Doc::Design);
    QMouseEvent ev(QEvent::MouseButtonPress, QPoint(0, 0), QPoint(0, 0), QPoint(0, 0),
                   Qt::LeftButton, Qt::NoButton, Qt::NoModifier);
    btn.mousePressEvent(&ev);
    QCOMPARE(m_doc->masterTimer()->m_functionList.size(), 0);
    QMouseEvent ev2(QEvent::MouseButtonRelease, QPoint(0, 0), QPoint(0, 0), QPoint(0, 0),
                    Qt::LeftButton, Qt::NoButton, Qt::NoModifier);
    btn.mouseReleaseEvent(&ev2);
    QCOMPARE(m_doc->masterTimer()->m_functionList.size(), 0);

    // Mouse button press in operate mode should toggle the function
    m_doc->setMode(Doc::Operate);
    btn.slotKeyPressed(QKeySequence(keySequenceB));
    // tell MasterTimer to process start queue
    m_doc->masterTimer()->timerTick();
    QCOMPARE(m_doc->masterTimer()->m_functionList.size(), 1);
    QCOMPARE(m_doc->masterTimer()->m_functionList[0], sc);
    QCOMPARE(sc->getAttributeValue(Function::Intensity), btn.startupIntensity());
    btn.slotKeyReleased(QKeySequence(keySequenceB));
    m_doc->masterTimer()->timerTick(); // Allow MasterTimer to take the function under execution
    QCOMPARE(sc->stopped(), false);
    QCOMPARE(btn.state(), VCButton::Active);

    QMouseEvent ev3(QEvent::MouseButtonPress, QPoint(0, 0), QPoint(0, 0), QPoint(0, 0),
                    Qt::LeftButton, Qt::NoButton, Qt::NoModifier);
    btn.mousePressEvent(&ev3);
    QCOMPARE(sc->m_stop, true);
    QCOMPARE(btn.state(), VCButton::Active);

    btn.slotFunctionStopped(sc->id());
    QCOMPARE(btn.state(), VCButton::Inactive);
    VCButton another(&w, m_doc);
    QVERIFY(btn.palette().color(QPalette::Button) != another.palette().color(QPalette::Button));
    QTest::qWait(500);
    QVERIFY(btn.palette().color(QPalette::Button) == another.palette().color(QPalette::Button));

    QMouseEvent ev4(QEvent::MouseButtonRelease, QPoint(0, 0), QPoint(0, 0), QPoint(0, 0),
                    Qt::LeftButton, Qt::NoButton, Qt::NoModifier);
    btn.mouseReleaseEvent(&ev4);
}

void VCButton_Test::flash()
{
    QWidget w;

    Scene* sc = new Scene(m_doc);
    m_doc->addFunction(sc);

    VCButton btn(&w, m_doc);
    btn.setCaption("Foobar");
    btn.setFunction(sc->id());
    btn.setAction(VCButton::Flash);
    btn.setKeySequence(QKeySequence(keySequenceB));
    btn.enableStartupIntensity(false);
    btn.setStartupIntensity(qreal(0.2));

    QSignalSpy spy(sc, SIGNAL(flashing(quint32,bool)));

    m_doc->setMode(Doc::Operate);
    btn.slotKeyPressed(QKeySequence(keySequenceB));
    QCOMPARE(m_doc->masterTimer()->m_functionList.size(), 0);
    QCOMPARE(btn.state(), VCButton::Active);
    QCOMPARE(sc->getAttributeValue(Function::Intensity), qreal(1.0));
    QCOMPARE(spy.size(), 1);
    QCOMPARE(spy[0][0].toUInt(), sc->id());
    QCOMPARE(spy[0][1].toBool(), true);

    btn.slotKeyReleased(QKeySequence(keySequenceB));
    QCOMPARE(btn.state(), VCButton::Inactive);
    QCOMPARE(spy.size(), 2);
    QCOMPARE(spy[1][0].toUInt(), sc->id());
    QCOMPARE(spy[1][1].toBool(), false);

    btn.slotFunctionFlashing(sc->id() + 1, true);
    QCOMPARE(btn.state(), VCButton::Inactive);

    m_doc->setMode(Doc::Design);
}

void VCButton_Test::input()
{
    QWidget w;

    Scene* sc = new Scene(m_doc);
    sc->setValue(0, 0, 255);
    sc->setFadeInSpeed(1000);
    sc->setFadeOutSpeed(1000);
    m_doc->addFunction(sc);

    VCButton btn(&w, m_doc);
    btn.setCaption("Foobar");
    btn.setFunction(sc->id());
    btn.setAction(VCButton::Flash);
    btn.enableStartupIntensity(true);
    btn.setStartupIntensity(qreal(1.0));
    btn.setInputSource(QSharedPointer<QLCInputSource>(new QLCInputSource(0, 0)));

    btn.slotInputValueChanged(0, 0, 255);
    QCOMPARE(btn.state(), VCButton::Inactive);

    m_doc->setMode(Doc::Operate);

    btn.slotInputValueChanged(0, 0, 255);
    QCOMPARE(btn.state(), VCButton::Active);

    btn.slotInputValueChanged(0, 0, 1);
    QCOMPARE(btn.state(), VCButton::Active);

    btn.slotInputValueChanged(0, 0, 0);
    QCOMPARE(btn.state(), VCButton::Inactive);

    btn.slotInputValueChanged(0, 0, 0);
    QCOMPARE(btn.state(), VCButton::Inactive);

    btn.slotInputValueChanged(0, 0, 1);
    QCOMPARE(btn.state(), VCButton::Active);

    btn.slotInputValueChanged(0, 0, 0);
    QCOMPARE(btn.state(), VCButton::Inactive);

    btn.setAction(VCButton::Toggle);

    btn.slotInputValueChanged(0, 0, 255);
    m_doc->masterTimer()->timerTick();
    QCOMPARE(btn.state(), VCButton::Active);
    QCOMPARE(sc->getAttributeValue(Function::Intensity), btn.startupIntensity());

    btn.slotInputValueChanged(0, 0, 0);
    QCOMPARE(sc->m_stop, false);

    btn.slotInputValueChanged(0, 0, 255);
    QCOMPARE(sc->m_stop, true);

    // Test that blackout gets toggled thru ext input
    btn.setAction(VCButton::Blackout);
    btn.slotInputValueChanged(0, 0, 1);
    QCOMPARE(m_doc->inputOutputMap()->blackout(), true);
    btn.slotInputValueChanged(0, 0, 0);
    QCOMPARE(m_doc->inputOutputMap()->blackout(), true);
    btn.slotInputValueChanged(0, 0, 255);
    QCOMPARE(m_doc->inputOutputMap()->blackout(), false);
    btn.slotInputValueChanged(0, 0, 0);
    QCOMPARE(m_doc->inputOutputMap()->blackout(), false);

    // Test that panic gets toggled thru ext input
    m_doc->masterTimer()->startFunction(sc);
    QCOMPARE(m_doc->masterTimer()->runningFunctions(), 1);
    m_doc->masterTimer()->start();
    btn.setAction(VCButton::StopAll);
    btn.slotInputValueChanged(0, 0, 1);
    QTest::qWait(100);
    QCOMPARE(m_doc->masterTimer()->runningFunctions(), 0);
    m_doc->masterTimer()->stop();
}

void VCButton_Test::setInput_data()
{
    QTest::addColumn<int>("input");
    QTest::newRow("mouse") << 0;
    QTest::newRow("keyboard") << 1;
    QTest::newRow("external") << 2;
}

void VCButton_Test::setInput()
{
    QFETCH(int, input);
    QWidget w;
    Scene* sc = new Scene(m_doc);
    sc->setValue(0, 0, 255);
    sc->setFadeInSpeed(1000);
    m_doc->addFunction(sc);

    VCButton btn(&w, m_doc);
    btn.setID(10);
    btn.setFunction(sc->id());
    btn.setAction(VCButton::SetOn);
    btn.setKeySequence(keySequenceA);
    btn.setInputSource(QSharedPointer<QLCInputSource>(new QLCInputSource(0, 0)));
    MasterTimer* timer = m_doc->masterTimer();
    QSignalSpy started(sc, SIGNAL(running(quint32)));
    auto press = [&]() {
        if (input == 0)
            QTest::mousePress(&btn, Qt::LeftButton);
        else if (input == 1)
            btn.slotKeyPressed(keySequenceA);
        else
            btn.slotInputValueChanged(0, 0, 127);
    };
    auto release = [&]() {
        if (input == 0)
            QTest::mouseRelease(&btn, Qt::LeftButton);
        else if (input == 1)
            btn.slotKeyReleased(keySequenceA);
        else
            btn.slotInputValueChanged(0, 0, 0);
    };

    // Design mode, unmatched input and NoteOff must not queue a start.
    press();
    QVERIFY(timer->m_startQueue.isEmpty());
    m_doc->setMode(Doc::Operate);
    btn.slotInputValueChanged(1, 0, 127);
    btn.slotInputValueChanged(0, 1, 127);
    btn.slotInputValueChanged(0, 0, 0);
    QVERIFY(timer->m_startQueue.isEmpty());

    press();
    QCOMPARE(timer->m_startQueue.size(), 1);
    QCOMPARE(timer->m_startQueue.first(), sc);
    QCOMPARE(sc->m_sources.size(), 1);
    QVERIFY(sc->m_sources.contains(btn.functionParent()));
    QVERIFY(!sc->stopped());

    // Repeated presses, including a release/press, before the timer starts
    // the function must not cancel the queued activation.
    press();
    release();
    press();
    QVERIFY(!sc->stopped());
    QCOMPARE(timer->m_startQueue.size(), 1);
    timer->timerTick();
    QCOMPARE(started.size(), 1);
    QCOMPARE(timer->m_functionList.size(), 1);
    QCOMPARE(timer->m_functionList.first(), sc);
    QVERIFY(sc->isRunning());

    // Stay inside the fade-in and verify duplicate selections do not reset it.
    timer->timerTick();
    timer->timerTick();
    const quint32 elapsed = sc->elapsed();
    QVERIFY(elapsed > 0);
    QVERIFY(elapsed < sc->fadeInSpeed());

    press();
    press();
    release(); // including MIDI NoteOff / zero velocity
    QCOMPARE(sc->elapsed(), elapsed);
    QVERIFY(timer->m_startQueue.isEmpty());
    timer->timerTick();
    QVERIFY(sc->elapsed() > elapsed);
    QVERIFY(!sc->stopped());
    QVERIFY(sc->isRunning());
    QCOMPARE(sc->m_sources.size(), 1);
    QVERIFY(sc->m_sources.contains(btn.functionParent()));
    QVERIFY(timer->m_startQueue.isEmpty());
    QCOMPARE(started.size(), 1);

    btn.setAction(VCButton::SetOff);
    btn.updateState(); // same state refresh performed by properties acceptance
    QCOMPARE(btn.state(), VCButton::Inactive);
    press();
    QVERIFY(sc->stopped());
    QVERIFY(sc->m_sources.isEmpty());
    release();
    press();
    timer->timerTick();
    QVERIFY(!sc->isRunning());
    QCOMPARE(btn.state(), VCButton::Inactive);
    QVERIFY(timer->m_startQueue.isEmpty());
}

void VCButton_Test::setOffMonitored_data()
{
    QTest::addColumn<bool>("takeOver");
    QTest::newRow("monitored") << false;
    QTest::newRow("set-on-takeover") << true;
}

void VCButton_Test::setOffMonitored()
{
    QFETCH(bool, takeOver);
    QWidget w;
    Scene* sc = new Scene(m_doc);
    sc->setValue(0, 0, 255);
    m_doc->addFunction(sc);
    VCButton monitor(&w, m_doc);
    monitor.setID(10);
    monitor.setFunction(sc->id());
    monitor.setAction(VCButton::SetOn);
    VCButton off(&w, m_doc);
    off.setFunction(sc->id());
    off.setAction(VCButton::SetOff);
    off.setKeySequence(keySequenceA);
    QSignalSpy starting(&off, SIGNAL(functionStarting(quint32,qreal)));
    QSignalSpy running(sc, SIGNAL(running(quint32)));
    m_doc->setMode(Doc::Operate);
    sc->start(m_doc->masterTimer(), FunctionParent::master());
    m_doc->masterTimer()->timerTick();
    QCOMPARE(monitor.state(), VCButton::Monitoring);
    QCOMPARE(off.state(), VCButton::Inactive);
    // SetOn must take ownership of a monitored attachment without restarting
    // the already-running scene, then remain idempotent on repeated presses.
    if (takeOver)
    {
        monitor.pressFunction();
        monitor.pressFunction();
        m_doc->masterTimer()->timerTick();
        QCOMPARE(monitor.state(), VCButton::Active);
        QVERIFY(sc->m_sources.contains(monitor.functionParent()));
        QCOMPARE(running.size(), 1);
    }
    off.slotKeyPressed(keySequenceA);
    off.slotKeyReleased(keySequenceA);
    off.slotKeyPressed(keySequenceA);
    QVERIFY(sc->stopped());
    QVERIFY(sc->m_sources.isEmpty());
    QCOMPARE(off.state(), VCButton::Inactive);
    QCOMPARE(starting.size(), 0);
    m_doc->masterTimer()->timerTick();
    QVERIFY(!sc->isRunning());
}

void VCButton_Test::setSolo_data()
{
    QTest::addColumn<bool>("pendingStop");
    QTest::newRow("completed-stop") << false;
    QTest::newRow("reselect-before-stop-with-fade") << true;
}

void VCButton_Test::setSolo()
{
    QFETCH(bool, pendingStop);
    QWidget w;
    VCSoloFrame frame(&w, m_doc);
    Scene* a = new Scene(m_doc);
    a->setValue(0, 0, 255);
    a->setFadeOutSpeed(pendingStop ? 25000 : 0);
    m_doc->addFunction(a);
    Scene* b = new Scene(m_doc);
    b->setValue(0, 1, 255);
    m_doc->addFunction(b);

    VCButton buttonA(&frame, m_doc);
    buttonA.setID(10);
    buttonA.setFunction(a->id());
    buttonA.setAction(VCButton::SetOn);
    buttonA.setInputSource(QSharedPointer<QLCInputSource>(new QLCInputSource(0, 0)));
    VCButton buttonB(&frame, m_doc);
    buttonB.setID(11);
    buttonB.setFunction(b->id());
    buttonB.setAction(VCButton::SetOn);
    buttonB.setInputSource(QSharedPointer<QLCInputSource>(new QLCInputSource(0, 1)));
    VCButton off(&frame, m_doc);
    off.setFunction(b->id());
    off.setAction(VCButton::SetOff);
    QSignalSpy starting(&off, SIGNAL(functionStarting(quint32,qreal)));

    m_doc->setMode(Doc::Operate);
    MasterTimer* timer = m_doc->masterTimer();
    buttonA.slotInputValueChanged(0, 0, 127);
    timer->timerTick();
    QVERIFY(a->isRunning());
    QVERIFY(a->m_sources.contains(buttonA.functionParent()));

    buttonB.slotInputValueChanged(0, 1, 127);
    QVERIFY(a->stopped());
    QVERIFY(a->m_sources.isEmpty());
    QVERIFY(b->m_sources.contains(buttonB.functionParent()));
    if (!pendingStop)
    {
        timer->timerTick();
        QVERIFY(!a->isRunning());
        QVERIFY(b->isRunning());
        QCOMPARE(buttonA.state(), VCButton::Inactive);
    }
    else
    {
        // Do not process the timer or deliver a synthetic stopped signal:
        // A is still Active while its stop/fade is pending, B is queued.
        QVERIFY(a->isRunning());
        QCOMPARE(buttonA.state(), VCButton::Active);
        QVERIFY(timer->m_startQueue.contains(b));
    }

    buttonA.slotInputValueChanged(0, 0, 127);
    // Reselection must reclaim real function ownership, not just keep the LED
    // active. In particular it must cancel A's pending stop and stop B.
    QVERIFY2(a->m_sources.contains(buttonA.functionParent()),
             "Reselecting A while its stop is pending must reclaim A's ownership");
    QVERIFY(!a->stopped());
    QVERIFY(b->stopped());
    timer->timerTick();
    timer->timerTick(); // also drain B if it was still queued on reselection
    QVERIFY(a->isRunning());
    QCOMPARE(buttonA.state(), VCButton::Active);
    QVERIFY(a->m_sources.contains(buttonA.functionParent()));
    QVERIFY(!b->isRunning());
    QCOMPARE(timer->m_functionList.size(), 1);
    QCOMPARE(timer->m_functionList.first(), a);

    // An Off button for B must neither announce a solo selection nor stop A.
    off.pressFunction();
    off.pressFunction();
    QVERIFY(!a->stopped());
    QVERIFY(a->m_sources.contains(buttonA.functionParent()));
    QCOMPARE(off.state(), VCButton::Inactive);
    QCOMPARE(starting.size(), 0);
}

void VCButton_Test::mixedSoloQueued_data()
{
    QTest::addColumn<bool>("toggleFirst");
    QTest::newRow("toggle-then-set-on") << true;
    QTest::newRow("set-on-then-toggle") << false;
}

void VCButton_Test::mixedSoloQueued()
{
    QFETCH(bool, toggleFirst);
    QWidget w;
    VCSoloFrame frame(&w, m_doc);
    Scene* a = new Scene(m_doc);
    a->setValue(0, 0, 255);
    m_doc->addFunction(a);
    Scene* b = new Scene(m_doc);
    b->setValue(0, 1, 255);
    m_doc->addFunction(b);
    VCButton buttonA(&frame, m_doc);
    buttonA.setID(10);
    buttonA.setFunction(a->id());
    buttonA.setAction(toggleFirst ? VCButton::Toggle : VCButton::SetOn);
    VCButton buttonB(&frame, m_doc);
    buttonB.setID(11);
    buttonB.setFunction(b->id());
    buttonB.setAction(toggleFirst ? VCButton::SetOn : VCButton::Toggle);
    QSignalSpy runningA(a, SIGNAL(running(quint32)));
    QSignalSpy selectingA(&buttonA, SIGNAL(functionStarting(quint32,qreal)));
    m_doc->setMode(Doc::Operate);
    MasterTimer* timer = m_doc->masterTimer();

    // Both activations are still queued when B cancels A. Draining the
    // cancelled start really emits running(), but must not reselect A.
    buttonA.pressFunction();
    buttonB.pressFunction();
    QCOMPARE(timer->m_startQueue.size(), 2);
    QVERIFY(a->stopped());
    QVERIFY(a->m_sources.isEmpty());
    QVERIFY(!b->stopped());
    QVERIFY(b->m_sources.contains(buttonB.functionParent()));
    QCOMPARE(selectingA.size(), 1);
    timer->timerTick();
    QCOMPARE(runningA.size(), 1);
    QCOMPARE(selectingA.size(), 1);
    QVERIFY(!b->stopped());
    QVERIFY(b->m_sources.contains(buttonB.functionParent()));
    timer->timerTick(); // remove cancelled A from the execution list
    QVERIFY(!a->isRunning());
    QCOMPARE(buttonA.state(), VCButton::Inactive);
    QCOMPARE(buttonB.state(), VCButton::Active);
    QCOMPARE(timer->m_functionList.size(), 1);
    QCOMPARE(timer->m_functionList.first(), b);

    // Both action combinations must still allow selecting A normally later.
    buttonA.pressFunction();
    QVERIFY(!a->stopped());
    QVERIFY(a->m_sources.contains(buttonA.functionParent()));
    QVERIFY(b->stopped());
    QVERIFY(b->m_sources.isEmpty());
    timer->timerTick();
    QVERIFY(a->isRunning());
    QVERIFY(!b->isRunning());
    QCOMPARE(timer->m_functionList.size(), 1);
    QCOMPARE(timer->m_functionList.first(), a);
}

void VCButton_Test::sharedAttachmentRestart()
{
    QWidget w;
    Scene* sc = new Scene(m_doc);
    sc->setValue(0, 0, 255);
    m_doc->addFunction(sc);
    VCButton toggle(&w, m_doc);
    toggle.setID(10);
    toggle.setFunction(sc->id());
    toggle.enableStartupIntensity(true);
    toggle.setStartupIntensity(qreal(0.4));
    VCButton on(&w, m_doc);
    on.setID(11);
    on.setFunction(sc->id());
    on.setAction(VCButton::SetOn);
    on.enableStartupIntensity(true);
    on.setStartupIntensity(qreal(0.4));
    m_doc->setMode(Doc::Operate);
    MasterTimer* timer = m_doc->masterTimer();
    toggle.pressFunction();
    timer->timerTick();
    on.pressFunction();
    QCOMPARE(toggle.state(), VCButton::Active);
    QCOMPARE(on.state(), VCButton::Active);
    const int toggleIntensity = toggle.m_intensityOverrideId;
    const int onIntensity = on.m_intensityOverrideId;
    QVERIFY(toggleIntensity != Function::invalidAttributeId());
    QVERIFY(onIntensity != Function::invalidAttributeId());

    // Request an attribute-preserving stop, then reselect before the timer
    // processes it. Restarting the same running Scene invokes postRun/preRun.
    sc->stop(FunctionParent::master(), true);
    on.pressFunction();
    QVERIFY(!sc->stopped());
    QVERIFY(sc->m_sources.contains(on.functionParent()));
    QSignalSpy stopped(sc, SIGNAL(stopped(quint32)));
    QSignalSpy toggleStates(&toggle, SIGNAL(stateChanged(int)));
    timer->timerTick();
    QCOMPARE(stopped.size(), 1); // a real intermediate stopped notification
    QVERIFY(sc->isRunning());
    QVERIFY(!sc->stopped());
    QCOMPARE(toggle.state(), VCButton::Active);
    QCOMPARE(on.state(), VCButton::Active);
    QCOMPARE(toggleStates.size(), 0);
    QCOMPARE(toggle.m_intensityOverrideId, toggleIntensity);
    QCOMPARE(on.m_intensityOverrideId, onIntensity);
    QCOMPARE(sc->getAttributeValue(Function::Intensity), qreal(0.4));
    QCOMPARE(timer->m_functionList.size(), 1);
    QVERIFY(timer->m_startQueue.isEmpty());
}

void VCButton_Test::setXML_data()
{
    QTest::addColumn<QString>("actionXML");
    QTest::addColumn<int>("action");
    QTest::newRow("missing") << QString() << int(VCButton::Toggle);
    QTest::newRow("legacy-toggle") << QString("<Action>Toggle</Action>") << int(VCButton::Toggle);
    QTest::newRow("set-on") << QString("<Action>SetOn</Action>") << int(VCButton::SetOn);
    QTest::newRow("set-off") << QString("<Action>SetOff</Action>") << int(VCButton::SetOff);
}

void VCButton_Test::setXML()
{
    QFETCH(QString, actionXML);
    QFETCH(int, action);
    QWidget w;
    VCButton btn(&w, m_doc);
    QBuffer input;
    input.setData(QString("<Button>%1</Button>").arg(actionXML).toUtf8());
    QVERIFY(input.open(QIODevice::ReadOnly | QIODevice::Text));
    QXmlStreamReader reader(&input);
    QVERIFY(reader.readNextStartElement());
    QVERIFY(btn.loadXML(reader));
    QVERIFY(!reader.hasError());
    QCOMPARE(int(btn.action()), action);

    QBuffer buffer;
    QVERIFY(buffer.open(QIODevice::WriteOnly | QIODevice::Text));
    QXmlStreamWriter writer(&buffer);
    QVERIFY(btn.saveXML(&writer));
    writer.setDevice(NULL);
    buffer.close();
    QVERIFY(buffer.open(QIODevice::ReadOnly | QIODevice::Text));
    QXmlStreamReader saved(&buffer);
    QVERIFY(saved.readNextStartElement());
    int actions = 0;
    while (saved.readNextStartElement())
    {
        if (saved.name() == "Action")
        {
            ++actions;
            QCOMPARE(saved.readElementText(), VCButton::actionToString(VCButton::Action(action)));
        }
        else
            saved.skipCurrentElement();
    }
    QCOMPARE(actions, 1);
    VCButton restored(&w, m_doc);
    QVERIFY(buffer.seek(0));
    QXmlStreamReader roundtrip(&buffer);
    QVERIFY(roundtrip.readNextStartElement());
    QVERIFY(restored.loadXML(roundtrip));
    QVERIFY(!roundtrip.hasError());
    QCOMPARE(int(restored.action()), action);
}

void VCButton_Test::setProperties()
{
    QWidget w;
    VCButton btn(&w, m_doc);
    {
        VCButtonProperties prop(&btn, m_doc);
        QVERIFY(!prop.m_setMode->isEnabled());
        prop.m_set->setChecked(true);
        QVERIFY(prop.m_setMode->isEnabled());
        QCOMPARE(prop.m_setMode->currentIndex(), 0);
        prop.accept();
    }
    QCOMPARE(btn.action(), VCButton::SetOn);
    {
        VCButtonProperties prop(&btn, m_doc);
        QVERIFY(prop.m_set->isChecked());
        QCOMPARE(prop.m_setMode->currentIndex(), 0);
        prop.m_flash->setChecked(true);
        QVERIFY(!prop.m_setMode->isEnabled());
        prop.m_blackout->setChecked(true);
        QVERIFY(!prop.m_setMode->isEnabled());
        prop.m_stopAll->setChecked(true);
        QVERIFY(!prop.m_setMode->isEnabled());
        prop.m_toggle->setChecked(true);
        QVERIFY(!prop.m_setMode->isEnabled());
        prop.m_set->setChecked(true);
        prop.m_setMode->setCurrentIndex(1);
        prop.reject();
    }
    QCOMPARE(btn.action(), VCButton::SetOn);
    {
        VCButtonProperties prop(&btn, m_doc);
        prop.m_setMode->setCurrentIndex(1);
        prop.accept();
    }
    QCOMPARE(btn.action(), VCButton::SetOff);
    {
        VCButtonProperties prop(&btn, m_doc);
        QVERIFY(prop.m_set->isChecked());
        QVERIFY(prop.m_setMode->isEnabled());
        QCOMPARE(prop.m_setMode->currentIndex(), 1);
        prop.m_setMode->setCurrentIndex(0);
        prop.accept();
    }
    QCOMPARE(btn.action(), VCButton::SetOn);
}

void VCButton_Test::paint()
{
    QWidget w;

    VCButton btn(&w, m_doc);

    w.show();
    btn.show();

    QTest::qWait(1);

    btn.setState(VCButton::Active);
    btn.update();
    QTest::qWait(1);
    btn.setState(VCButton::Inactive);
    btn.update();
    QTest::qWait(1);
    btn.setIconPath("../../../resources/icons/png/qlcplus.png");
    btn.update();
    QTest::qWait(1);
    btn.setCaption("Foobar");
    btn.update();
    QTest::qWait(1);
    btn.setAction(VCButton::Flash);
    btn.update();
    QTest::qWait(1);
    m_doc->setMode(Doc::Operate);
    btn.update();
    QTest::qWait(1);
}

void VCButton_Test::toggleAndFlash()
{
    QWidget w;

    Scene* sc = new Scene(m_doc);
    m_doc->addFunction(sc);

    VCButton toggleBtn(&w, m_doc);
    toggleBtn.setFunction(sc->id());
    toggleBtn.setAction(VCButton::Toggle);
    toggleBtn.setKeySequence(QKeySequence(keySequenceA));

    VCButton flashBtn(&w, m_doc);
    flashBtn.setFunction(sc->id());
    flashBtn.setAction(VCButton::Flash);
    flashBtn.setKeySequence(QKeySequence(keySequenceB));

    m_doc->setMode(Doc::Operate);

    // push toggle button
    toggleBtn.slotKeyPressed(QKeySequence(keySequenceA));
    // tell MasterTimer to process start queue
    m_doc->masterTimer()->timerTick();
    QCOMPARE(toggleBtn.state(), VCButton::Active);
    QCOMPARE(flashBtn.state(), VCButton::Inactive);

    // push flash button
    flashBtn.slotKeyPressed(QKeySequence(keySequenceB));
    QCOMPARE(toggleBtn.state(), VCButton::Active);
    QCOMPARE(flashBtn.state(), VCButton::Active);

    // flash button released
    flashBtn.slotKeyReleased(QKeySequence(keySequenceB));
    QCOMPARE(toggleBtn.state(), VCButton::Active);
    QCOMPARE(flashBtn.state(), VCButton::Inactive);

    // push toggle button once more
    toggleBtn.slotKeyPressed(QKeySequence(keySequenceA));
    // tell MasterTimer to process start queue
    m_doc->masterTimer()->timerTick();
    QCOMPARE(toggleBtn.state(), VCButton::Inactive);
    QCOMPARE(flashBtn.state(), VCButton::Inactive);
    QCOMPARE(sc->m_stop, true);
    toggleBtn.slotFunctionStopped(sc->id());
}

QTEST_MAIN(VCButton_Test)

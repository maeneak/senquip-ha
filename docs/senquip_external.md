# External Sensors[](#external-sensors "Permalink to this heading")

## Inputs and Outputs[](#inputs-and-outputs "Permalink to this heading")

The Senquip QUAD has 5 multifunction Input/Outputs that can be individually configured.

| Pin | Channel |
| --- | --- |
| 3   | IO 1 |
| 4   | IO 2 |
| 5   | IO 3 |
| 6   | IO 4 |
| 7   | IO 5 |

Each of the 5 IO can measure:

*   analog voltages,
    
*   currents into and out of the terminals,
    
*   frequencies,
    
*   pulses,
    
*   duty cycle,
    
*   digital ON or OFF state.
    

Each measurement can be calibrated and alerts of type info, alert, warning, and alarm can be set.

The IO can also be used as outputs and can be switched to:

*   OFF - high impedance,
    
*   Vin - connected via a switch to Vin,
    
*   GND - connected via a switch to GND,
    
*   Vset - connected to an internal configurable voltage source,
    
*   PULLUP - an internal pullup resistor is enabled.
    

Vset is an internal voltage source that can be configured in _General IO_ settings to be between 5V and 25V. Vset is typically used to power external sensors. Vset is backed up by the internal LiPo battery and so will continue to operate if power to the device is intermittent, for instance if powered by solar. The setting for Vset voltage is used to control the feedback loop of a boost converter acording to a set of characterisation data. The voltage that appears on the output may vary by approximately 100mV.

A short dead-time is inserted when switching between IO states to prevent high current flows during the transition from Vin and Vset to ground and ground to Vin and Vset states.

The input and output functionality are independant and can be enabled simultaneously. You can for instance switch an output to Vin, measure the voltage on the output to confirm and measure the current flowing into the output.

Each IO pin can supply up to 100mA from either Vin or Vset and can sink 250mA to ground. The IO are able to switch inductive loads such as relays; it is recommended that flyback diodes always be used with inductive loads. The inputs are protected against over-voltage events to 85V and against static discharge.

Note

Vset can provide a maximum of 100mA across all IO pins.

All parameters are measured at the same time, so for instance an input can report measuring 15V with a 20mA current flowing. Settings are available to limit which of the measured parameters are transmitted at the end of each measurement cycle. Limit the data sent at the end of a measurement cycle by only selecting the measurement types that you require.

A simplified internal architecture of the IO module is shown below.

[![Single current sensor](../../_images/io_architecture.jpg)](../../_images/io_architecture.jpg)

Simplified internal IO architecture[](#id5 "Permalink to this image")

IO1 and IO2 can be configured to cause the device to exit sleep or hibernate mode when a change is detected.

If the Senquip device is reset, the IO states are unaffected. They hold their state until a change is applied. For example, if new script is loaded, forcing a reset, the IO state is held until the new script applies a change. In the case of a processor malfucntion, the IO state will be reset after 30 seconds. IO states are reset to the default of off when entering hibernate or sleep.

### Powering external devices[](#powering-external-devices "Permalink to this heading")

IO on the Senquip QUAD can be used to power and provide signals to external sensors, relays, lights, buzzers, and other devices. To permanently power an external device by supplying it with a voltage, set the IO _Default State_ to _VIN_ or _VSET_ in which case the connected device will be permanently powered. To power a device by connecting it to ground, select _GND_ as the _Default State_. The default state will continue to be applied between measurement cycles.

Alternatively, the IO can made to switch power on only at a measurement cycle, and for a defined period. To enable switched power, set the default for the IO to _OFF_ and enable the _Measurement State_ as _VIN_ or _VSET_. Set the _Measurement Time_ as the time for which the externally connected sensor must be powered before being measured. This time is typically the boot time for a sensor. In this case, Vin or Vset will only be made available on the IO during a measurement interval and for the time specified. This is the preferred method for installs that are solar powered or have intermittent power. Measurement of CAN, RS232, and RS485 are delayed by the longest of all specified measurement times to allow for the case where an IO is being used to power a serially connected device.

The figure below shows an RS232 sensor that is powered by IO5 and measured on the RS232 port and a relay that is energised by setting an IO to ground.

[![Single current sensor](../../_images/io_powering.jpg)](../../_images/io_powering.jpg)

Powering external devices on an IO[](#id6 "Permalink to this image")

Note

Where switched power is used to power a sensor that is read by another input, the _Measurement Time_ specified for the IO and the input must be the same to ensure that the sensor is powered when measured.

For advanced users, the state of an IO can be switched from within a script. This allows for the control of complex sensors and systems and precise timing. If changes to the IO are made from within a script, the default settings will only be re-applied the next time the device boots.

Warning

If an IO is enabled in the settings, and is used in a script, the behaviour of that IO will be affected by both the settings and the script.

Note

In hibernate and sleep, the outputs default to _OFF_ and the internal voltage booster is off. If a pullup has been enabled, it will remain on in sleep and hibernate.

### Current Measurement[](#current-measurement "Permalink to this heading")

Loop powered (2-wire) and externally powered (3-wire) 4-20mA devices can be used with the Senquip QUAD.

For 2-wire devices, Vin or Vset power can be supplied by an IO and the current drawn measured by that same IO. A typical 2-wire install is shown in the figure below.

[![2-wire current sensor conection](../../_images/io_2-wire.jpg)](../../_images/io_2-wire.jpg)

2-wire 4-20mA device install[](#id7 "Permalink to this image")

3-wire devices are externally powered as they typically draw more than 4mA at a minimum and so are not suitable for loop powering. The Senquip QUAD can power a 3-wire device with Vin or Vset from one IO and measure the output current on a second IO. A typical 3-wire install in shown in the figure below.

[![3-wire current sensor connection](../../_images/io_3-wire.jpg)](../../_images/io_3-wire.jpg)

3-wire 4-20mA device install[](#id8 "Permalink to this image")

Current out of the IO terminal is defined as positive (2-wire) and current into the terminal (3-wire) is defined as negative. Although optimised for 4-20mA, the IO can measure currents in the range -100mA to 100mA.

### Pulse Count Measurement[](#pulse-count-measurement "Permalink to this heading")

The Senquip QUAD can count pulses from devices like water-meters, rain guages, and speed-sensors. The inputs can be from voltage free contacts like reed switches, hall effect sensors, or pulse trains from powered devices. When connecting to voltage free switches, am optional pullup (wetting) resistor can be enabled in the settings. The Senquip QUAD can count pulses while awake and between cycles when sleeping. Although all IO can count in a very low power mode, IO1 and IO2 have additional circuitry that allows ultra low power pulse counting. Along with a total pulse count, frequency and duty cycle are also measured at the measurement interval.

The figure shows how to wire a voltage free contact and powered pulse train to the Senquip QUAD IO.

[![Diagram showing connections to measure pulses](../../_images/io_pulse.jpg)](../../_images/io_pulse.jpg)

Pulse counting[](#id9 "Permalink to this image")

**Calibration**

Calibration can be applied to each measurement so that the value returned by the Senquip QUAD is in units that are meaningful in the end application. For instance, a fuel level sensor that outputs a voltage between 0 and 5V may represent a level between 0 and 100 litres of diesel. The voltage measurement can be calibrated to convert from Volts to the more meaningful unit of litres.

In any system, the measurement instrument (the Senquip QUAD), the sensor and possibly the measured value will be subject to errors that may accumulate to reduce accuracy. In a system that measures fluid volume in a 100 litre tank using a 4-20mA sensor, offset errors may result in a non-zero or negative reading when the tank is empty. Sensor gain may also not be perfectly linear and so a 1 litre change may be measured differently when the tank is empty versus when it is full. The sensor may report in inches of liquid height where a more meaningful unit may be litres. To achieve an accurate and meaningful measurement, a calibration can be performed.

In this example, the tank could be calibrated by adding a small amount of liquid, say 10 litres at which point the current measured may be 4.1mA. Now add more liquid to take the level to say 80l. The sensor now reads 16.2mA. The calibration would then be filled into the IO setting as shown below:

|     |     |     |
| --- | --- | --- |
| Low In | 4.1 | This is the value in mA measured by the Senquip QUAD |
| Low Out | 10  | This is the actual value that we would like to report |
| High In | 16.2 | This is the value in mA measured by the Senquip QUAD |
| Low Out | 80  | This is the actual value that we would like to report |
| Unit | l   | The unit to be reported is litres |

**Warnings and Alarms**

For each measurement type, high and low warning and alarm levels can be set. Once enabled, each time a measurement is completed, the returned value will be compared with low and high _warning_ and _alarm_ thresholds. If a _warning_ or _alarm_ level is breached, a message will immediately be transmitted. As long as the _warning_ or _alarm_ condition persists, messages will be transmitted at the _exception-interval_ rather than the _transmit-interval_.

Note

If calibration has been applied, then the warning and enable thresholds should be set in the calibrated units.

To set a high level warning or alarm level only, set the low level to a value that is impossible to achieve. For instance to set a high only warning at 50V, set the low warning to -1V which is an unachievable value.

Hysteresis can be specified in increments of the specified unit, to prevent multiple alarms in the presence of electrical noise.

[![Hysteresis](../../_images/io_hysteresis.png)](../../_images/io_hysteresis.png)

Hysteresis[](#id10 "Permalink to this image")

### Specification[](#specification "Permalink to this heading")

| Parameter | Specification |
| --- | --- |
| _Output_ |     |
| Maximum Vin source current | 100mA per pin |
| Maximum Vset source current | 100mA per pin, 100mA total from Vset |
| Maximum GND sink current | 250mA per pin |
| Pullup resistor | 33k to 3.3V |
| _Input_ |     |
| Voltage ADC Type | 5 x 16 bit sigma delta |
| Voltage range | 0-75VDC |
| Voltage measurement precision | 3.125mV |
| Voltage measurement accuracy (0-5V, as measured) | +-0.005V |
| Voltage measurement accuracy (0-75V, as measured) | +-0.1V |
| Current ADC Type | 5 x 16 bit sigma delta |
| Current maximum positive (out) | 100mA |
| Current maximum negative (in) | +-100mA |
| Maxiumum measurable positive current | 80mA |
| Maxiumum measurable negative current | \-80mA |
| Current precision | 2.5uA (15 bits across 80mA) |
| Accuracy (4-20mA, as measured) | +-0.05mA |
| Accuracy (-100-100mA, as measured) | +-0.1mA |
| Pulse counting voltage threshold | 2.0V |
| Pulse counting maximum frequency in sleep (tested for IO1 and IO2) | 100Hz |
| Pulse counting maximum frequency always on (tested for IO1 and IO2) | 5kHz |
| Pulse minimum width | 1msec |
| Frequency measurement range (tested for IO1 and IO2) | 0.5Hz to 5kHz |
| Frequency measurement precision (tested for IO1 and IO2) | 1%  |
| Duty cycle measurement range (tested for IO1 and IO2) | 0% to 100% |
| Duty cycle precision (tested for IO1 and IO2) | +-0.5% (0.5Hz to 500Hz) |
| IO terminal input impedance | \>250k ohms |
| Threshold to wake from hibernate | \>2.3V |
| Threshold to enter hibernate | <1.0V |

[![Chart showing IO measurement accuracy over 0-5V](../../_images/io_accuracy.jpg)](../../_images/io_accuracy.jpg)

Voltage accuracy across all IO channels[](#id11 "Permalink to this image")

### Settings[](#settings "Permalink to this heading")

Each IO block has an identical set of settings.

Measurements can be scheduled as a multiple of the base-interval. The fastest possible measurement rate is achieved by setting the _Interval_ to 1 in which case measurements will occur on every base interval. To reduce power consumption, the measurement rate can be turned down by increasing the _Interval_. To turn an IO block off, set the _Interval_ to 0.

If the _Wake on Low to High_ option is selected, the device will wake from hibernate on a low to high voltage transition. If the _Hibernate on High to Low_ option is selected, the device will entern hibernate mode after _Hibernate Delay Intervals_ number of base intervals.

The _Default State_ can be selected as _OFF_, _GND_, _VIN_, _VSET_, and _PULLUP_.

The _Measurement State_ can selected as _NO CHANGE_, _GND_, _VIN_, and _VSET_. Where a measurement state is specified, a _Measurement Time_ must be selected.

Each voltage, current, frequency, duty-cycle, pulse and digital measurement can be individually _Enabled_ has an associated calibartion and alert settings.

A full list of IO settings is given in the table at the end of this chapter.

## Serial interface[](#serial-interface "Permalink to this heading")

The serial port can be used to capture data that is sent from an external system or to interface to a MODBUS sensor.

The serial port occupies pins 6 and 7 on the interface header. The pins have functions that depend on the chosen interface as shown in the table below. When RS485 mode is chosen, an optional 120Ω termination resistor can be selected.

| Interface type | Pin 6 function | Pin 7 function |
| --- | --- | --- |
| RS232 | Receive (Rx) | Transmit (Tx) |
| RS485 | RS485-B | RS485-A |

Note

RS485-B is sometimes referred to as D+ or TX+/RX+ and RS485-A as D- or TX-/RX-.

The RS485 receiver supports up to 256 nodes per bus, and features full failsafe operation for floating, shorted or terminated inputs. Interface pins are protected against electrostatic discharge up to 26kV, whether the QUAD is powered or unpowered.

### Specification[](#id1 "Permalink to this heading")

| Parameter | Specification |
| --- | --- |
| RS232 transmitter output low voltage (typical) | \-5.5V |
| RS232 transmitter output high voltage (typical) | +5.9V |
| RS232 Input threshold voltage | +1.5V |
| RS485 differential output voltage (minimum with load resistance 120Ω) | +2V |
| RS485 differential input signal threshold | +-220mV |
| Maximum nodes in RS485 mode | 256 |
| RS485 termination resistor | 120Ω |

### Settings[](#id2 "Permalink to this heading")

Measurements can be scheduled as a multiple of the base-interval. The fastest possible measurement rate is achieved by setting the _interval_ to 1 in which case measurements will occur on every base interval. To reduce power consumption, the measurement rate can be turned down by increasing the _interval_.

In _serial capture_ mode the measurement interval can be used to reduce the number of readings being provided by a connected sensor or system that may be permanently powered. If for instance, a connected system is sending a message every second but it is only required to be read and transmitted every minute, the measurement interval can be set to 1 minute in which case the device will wake on the minute interval, receive a message and return to sleep thereby missing the other 59 messages sent by the attached system. Since serial packets cannot be interrogated by the Senquip QUAD without a customised script, it makes sense to set the measurement interval to the same as the transmit interval in most cases.

The serial port on the Senquip QUAD can be configured as an RS232 or RS485 hardware interface using the _type_ option.

If RS485 mode is selected, an optional 120Ω termination resistor can be selected by selecting the _Termination resistor_ option. The purpose of the termination resistor is to match the impedance of a transmission line to the hardware impedance of the interface to which it is connected. Termination is generally not required in lower speed networks (9600 baud or less) and networks shorter than 500m in length. No more than 2 termination resistors should be used, one at each end of the RS485 transmission line.

A _baud rate_ of 4800, 9600, 19200, 38400, 56800 or 115200 needs to be selected using the _baud rate_ option. Other settings, including the number of bits, odd or even parity and 1 or 2 stop bits are added in the _settings_ field. The most common setup is 8 bits, no parity and 1 stop bit or “8N1”.

The serial interface can be configured in serial capture mode or [MODBUS](glossary.html#term-MODBUS) mode using the _mode_ option. Capture mode is typically used where an external sensor sends serial data and a portion of that serial data is to be captured. MODBUS mode is used to connect to external sensors that are compatible with the MODBUS standard.

In _serial capture mode_ The device listens for periodic data and when received, transmits this data at the next send interval. The maximum length of a message that can be captured is 512 characters. Once 512 characters have been received, the Senquip QUAD will terminate the capture and will transmit it on the next transmit interval.

In capture mode, the _max-time_ setting can be used to set a timeout after which the serial port will return to sleep. _Max-time_ can be used as a way to end serial measurement in the event that no serial data is received, or as a mechanism to allow the device to sample the serial port for a defined time-period.

Note

If the serial port needs to be kept on all the time, set the _max-time_ to longer than the measurement interval. The contents of the serial buffer is retained as long as the device does not return to sleep.

The operation of the _max chars_ option is similar to the _max time_ setting except that the serial port stops sampling after a certain number of characters has been received. In most cases where the _max-chars_ setting is used to terminate serial capture, the _max-time_ setting is also used to end the serial measurement in the event that data does not arrive.

In _Serial capture mode_, in systems where many messages are sent and only a few are of interest, a _start string_ of up to 10 characters can be enabled. For instance, in a typical GPS serial NMEA feed, the following are a subset of available messages:

*   DTM - Datum being used.
    
*   GGA - Fix information
    
*   GLL - Lat/Lon data
    
*   GSA - Overall Satellite data
    
*   GSV - Detailed Satellite data
    
*   RMC - Recommended minimum data for GPS
    
*   RTE - Route message
    
*   VTG - Vector track an Speed over the Ground
    

If in the application, the user is only interested in receiving the GGA message, then a _start string_ can be set to GGA. In that way, any messages starting with DTM, GLL, GSA or other unwanted messages will be discarded.

Note

If a start string is enabled, the device will stay awake until the string is received or until the _max-time_ is reached.

In firmware revisions less than 2, serial _start strings_ are specified as text, with special characters such as carriage return and line feed being specified by their respective escape sequences. A list of allowable escape sequences is given below:

*   \\f Form-feed
    
*   \\n Newline (Line Feed)
    
*   \\r Carriage Return
    
*   \\t Horizontal Tab
    
*   \\v Vertical Tab
    
*   \\\\ Backslash
    

Note

Because escape sequences start with a backslash (\\), if a capture string contains a backslash, it needs to be escaped and so is represented as a double backslash (\\\\).

In firmware release 2 and above, serial _start strings_ are specified as text, with special characters such as carriage return and line feed being specified by their respective ASCII codes in hexadecimal. A list of example hexadecimal sequences is given below:

*   \\x0C Form-feed
    
*   \\x0A Newline (Line Feed)
    
*   \\x0D Carriage Return
    
*   \\x09 Horizontal Tab
    
*   \\x0B Vertical Tab
    
*   \\x08 Backslash
    

The change to the method used to represent special characters has been made to allow for all ASCII characters to be used, and to allow for hexadecimal data to be captured.

Note

In firmware revisions 2 and lower, special characters are specified as escape characters. In revisions 2 and above, special characters are represented by their ASCII representations in hexadecimal.

In some serial protocols, the start of a packet is specified by a preceding period of inactivity on the serial bus. The _Idle Time Before Start_ parameter can be used to specify an idle time, which is exceeded will trigger the serial port to start capturing serial data.

Note

If the serial port is capturing data and a subsequent idle time occurs, the capture process will restart and captured data will be discarded.

A serial capture _stop string_ of up to 10 characters can also be provided. Again using the NMEA example, all NMEA messages end with a carriage return and line feed and so the serial capture _stop strings_ in each case will be the same and will be “\\r\\n” or \\x0D\\x0A in revision 2 and above firmware. In most instances, the serial _stop strings_ will be the same for all messages.

Note

If a _start string_ is specified without a _stop string_, or the _stop string_ is never encountered, the serial port will capture characters until the _max-time_ or _max-chars_ is reached, the next measurement interval occurs or 256 characters are received.

An optional serial _request string_ can be sent, on each measurement interval, to an external device. The purpose of the _request sting_ is to request data from an external sensor or system. The _request string_ can be a maximum of 10 characters and can be entered as text. Special characters like carriage return and line feed can be inserted using escape sequences or their ASCII representations as described earlier in the chapter.

The Senquip QUAD implements the _MODBUS_ communications protocol standard as a master, which enables communication with many slave devices connected to the network. The Senquip QUAD can be configured to periodically request specific data from slave _MODBUS_ devices on the network and transmit that data at specified intervals.

Up to fifty MODBUS data requests can be configured; these data requests can either be from individual slave devices or multiple requests from the same device. For each of the fifty data reads, the _slave address_, _function_ and _register address_ need to be specified. The _slave address_ will be specified by the manufacturer of the device that is attached to the Senquip QUAD; in some cases, slave devices allow their addresses to be configured. The _function_ specifies the type of data to be read from the slave device. The Senquip QUAD supports the following types of data reads:

*   Disabled - the particular MODBUS channel is not used
    
*   Read Coil - a 1 bit data value
    
*   Read Discrete - a 1 bit data value
    
*   Read Holding - a single 16 bit holding register
    
*   Read Input - a 16 bit input register
    
*   Read Holding (32 bits, Little Endian register order) - a 32 bit holding register
    
*   Read Holding (32 bits, Big Endian register order) - a 32 bit holding register
    
*   Read Input (32 bits, Little Endian register order) - a 32 bit input register
    
*   Read Input (32 bits, Little Endian register order) - a 32 bit input register
    

Endianness is the order or sequence of bytes of digital data in computer storage and will be specified by the sensor that is being connected to the QUAD.

A single MODBUS device may have multiple data values that can be read. The _register address_ specifies which data the slave device needs to deliver.

In _MODBUS mode_, calibration can be applied so that the registers read by the Senquip QUAD can be scaled to be in the units of what is being measured. For instance, a register that returns 0 to 255 may represent 0% humidity to 100% humidity. The Senquip QUAD can be calibrated to take a number and to convert it to humidity in % and return that as the measured value.

In any system, the sensor and possibly the measured value will be subject to errors that may accumulate to reduce accuracy. In a system that uses the Senquip QUAD to measure fluid volume in a 100 litre tank using a MODBUS sensor, the sensor may have offset errors such that with zero liquid in the tank, the Senquip QUAD is showing a small volume. The Senquip QUAD and sensor may also not be perfectly linear in that they may not measure 1 litre in exactly the same way when the tank is empty versus when it is full. The tank itself may also not be perfectly manufactured and may, for instance have walls that are not perfectly straight. All of these errors could add together such that the final system is less accurate than expected. To achieve a more accurate system, a calibration can be performed. In this example, the tank could be calibrated by adding a small amount of liquid, say 10 litres (low Y) and noting the value reported by the Senquip QUAD (low X). Now fill the tank by adding another 99 litres (high y) and note the value being reported by the Senquip QUAD (high X). By filling the high and low X and Y values into the calibration constants associated with _analog mode_, offset and non-linearity errors can be eradicated, resulting in a much more accurate system.

In _MODBUS mode_, _warning_ and _alarm_ thresholds for can be set for each MODBUS channel. Once enabled, each time a measurement is completed, the returned value will be compared with minimum and maximum _warning_ and _alarm_ thresholds. If a _warning_ or _alarm_ level is breached, a message will immediately be transmitted. As long as the _warning_ or _alarm_ condition persists, messages will be transmitted at the exception-interval rather than the transmit-interval.

Note

If calibration has been applied, then the warning and enable thresholds are in the calibrated units.

A full list of serial interface settings is given in the table at the end of the chapter.

## CAN Bus interface[](#can-bus-interface "Permalink to this heading")

The Senquip QUAD-C2 has two CAN bus interfaces that can be used to read data from all kinds of vehicles and sensors that use CAN as their communications medium. Hundreds of sensors can be connected to a single CAN network.

In many cases, the protocol that is being used on the CAN bus is known, and so large volumes of understandable data can be extracted from all kinds of vehicles. Common CAN protocols include:

*   J1939, the dominating CAN-based protocol for trucks and busses.
    
*   ISO 11783, a J1939 flavor for agricultural tractors.
    
*   ISO 11992, an interface between trucks and trailers.
    
*   NMEA 2000, a protocol based on J1939 for marine use.
    
*   CANopen, provides a standard for industrial machinery commonly used in industrial automation.
    

The Senquip QUAD is future proof and will be compatible with the CAN Flexible Data-rate (FD) specification.

Pins 11 and 12 on the Senquip QUAD header are for the CAN1 interface with pin 11 being CAN High (dominant high) and pin 12 being CAN Low (dominant low). Pins 13 and 14 on the Senquip QUAD header are for the CAN2 interface with pin 13 being CAN High (dominant high) and pin 14 being CAN Low (dominant low).

In CAN networks, 120Ω terminating resistors are found at each end of the network. In most systems, the terminating resistors will already be in place and will not be needed. In cases where a sensor network is being formed between an Senquip QUAD and external sensor, a 120Ω resistor should be placed between the CAN-H and CAN-L terminals on the Senquip QUAD.

Warning

In CAN bus systems, the ground supplied to the Senquip QUAD must be the same ground as used by the CAN network. High differential voltages between the CAN lines and ground can damage the CAN interface.

### Specification[](#id3 "Permalink to this heading")

| Parameter | Specification |
| --- | --- |
| CAN High driver voltage (typical) | 2.9V |
| CAN Low driver voltage (typical) | 0.9V |
| Common mode voltage for reception (maximum) | +-25V |
| Absolute maximum voltage on CAN High and CAN Low | +-60V |
| Termination resistor | 120Ω |

### Settings[](#id4 "Permalink to this heading")

Measurements can be scheduled as a multiple of the base-interval. The fastest possible measurement rate is achieved by setting the _interval_ to 1 in which case the CAN network will be sampled on every base interval. To reduce power consumption, the measurement rate can be turned down by increasing the _interval_.

The CAN bus peripheral on Senquip devices supports can bit rates of 125, 250, 500 and 1000 bits per second as specified in the _Nominal Baud Rate_ field.

To ensure minimum intrusion on CAN systems, the CAN peripheral can be set to listen only. In this mode the Senquip device will only receive messages that are acknowledged on the bus by a listening node. Where required, the Senquip device can be made to acknowledge messages by selecting the _TX Enable_ option.

The _Capture Time_ setting can be used to set a timeout after which the CAN bus peripheral will stop listening, allowing the Senquip device to transmit received messages and return to sleep. _Capture-time_ can also be used as a mechanism to allow the CAN peripheral to sample the CAN bus for a defined time-period.

A full list of CAN bus settings is given in the table at the end of this chapter.

### CAN Filters[](#can-filters "Permalink to this heading")

Most automotive CAN networks transmit hundreds of different messages, each with a unique identifier. The Senquip device allows you to filter and capture only the messages you need using the _ID Capture List_.

**Basic Usage**

Enter the CAN IDs you want to capture in _hexadecimal_, separated by commas. For example:

18FF20F2,18FF36F0,18FF1BF2

During each measurement interval, the device listens for the listed messages until either all are received or the _Capture Time_ expires.

**Capturing Multiple Messages**

To capture multiple messages with the same ID, use `*` followed by the number of each message requied:

18FF20F2\*4,18FF1BF2\*10

This captures:

*   4 messages with ID `18FF20F2`
    
*   10 messages with ID `18FF1BF2`
    

To capture all messages of a certain ID received during the interval, use `*` without a number:

18FF1F12\*

**Wildcards and Advanced Filters**

*   `??` can replace the **Priority** or **Source Address** in a J1939 ID.
    
    For example:
    
    ??FECA??
    
    This matches any J1939 message with a PGN of `FECA`, regardless of Priority or Source Address.
    
*   `#` can be placed at the end of the list to match one of any other message not already listed:
    
    18FE1451\*4,18FE1256\*2,#
    
    This captures:
    
    *   4 messages with ID `18FE1451`
        
    *   2 messages with ID `18FE1256`
        
    *   1 of every other unique ID not already matched
        

**Special Cases**

*   Leave the list `blank` to capture one of every message that arrives.
    
*   Use a single `*` to capture all messages, in the order they arrive.
    
    Warning
    
    Capturing all messages may overwhelm the device in high-traffic CAN systems.
    

### Sending CAN Messages[](#sending-can-messages "Permalink to this heading")

CAN messages can be sent to connected device from within a script. The messages can be sent once, or can be set to repeat at a given time interval. If the device enters sleep or hibernate, repeating messages will be stopped. If the Senquip device is reset, the sending of repeating CAN messages is unaffected. The messages will continue to be sent until a change is applied. For example, if new script is loaded, forcing a reset, the CAN messages will continue to be sent until the new script applies a change. In the case of a malfunction that lasts for more than 30 second, repeating CAN messages will be stopped.

> Note
> 
> To send CAN messages, the _TX Enable_ option must be selected.

## External Sensor Settings[](#external-sensor-settings "Permalink to this heading")

A full list of settings for external sensors is given in the table below.

     
| Name | Item | Function | Range | Unit | Internal Reference |
| --- | --- | --- | --- | --- | --- |
| **Input 1** |     |     |     |     |     |
| Name | text | A name for the input that is meaningful to the user. | 25 chars |     | input1.name |
| Interval | integer | The number of base intervals after which the input is sampled. A value of 1 means that the input is collected every base interval. Set to 0 to disable. | 0 to 10000 |     | input1.interval |
| Mode | preset | Specifies the function of the IN1 terminal. The calibration, warnings and alarms are applied to this mode. |     |     | input1.mode |
| **Digital 1** |     |     |     |     |     |
| Digital Threshold | decimal | A threshold against which the input is compared to determine if the input state is ON or OFF. | 0 to 30 | Volts | input1.digital.threshold |
| Digital Hysteresis | decimal | Once the input is in a certain state, hysteresis is the amount by which the input has to change before moving to the other state. | 0 to 20 | Volts | input1.digital.hysteresis |
| Count Hours | boolean | Counts the number of hours the digtial input is ON (above threshold). |     |     | input1.digital.count\_hours |
| Digital Change Alert | boolean | Sets whether a change in digital state generates an alert. |     |     | input1.digital.alert.enable |
| Analog 1 Calibration | text | Calibration parameters for Analog 1. Refer to user guide. | 30 chars |     | input1.cal |
| Unit | text | The unit of measure associated with the calibration. Examples: Litres/min, RPM, Volts |     |     | input1.unit |
| Warning | text | Warning thresholds. Refer to user guide. |     |     | input1.warning |
| Alarm | text | Alarm thresholds. Refer to user guide. |     |     | input1.alarm |
| Alarm/Warning Hysteresis | decimal | Once the input is in a certain state, hysteresis is the amount by which the input has to change before moving to the other state. |     |     | input1.hysteresis |
| **Pulse Input** |     |     |     |     |     |
| Pulse Counting | boolean | Enables counting of pulses in addition to frequency measurement. |     |     | input1.pulse.enable |
| Reset Value | integer | The value at which the number of pulses counted on the input is reset to zero. | 1 to 2000000000 | Counts | input1.pulse.reset\_value |
| Pulse Scaling | decimal | Multiplier to convert the pulse count to a useful unit. |     |     | input1.pulse.scaling |
| Pulse Unit | text | The unit of measure associated with the scaled pulse count. Eg: Litres |     |     | input1.pulse.unit |
| Pulse Warning | text | Warning thresholds. Refer to user guide. |     |     | input1.pulse.warning |
| Pulse Alarm | text | Alarm thresholds. Refer to user guide. |     |     | input1.pulse.alarm |
| **Input 2** |     |     |     |     |     |
| Name | text | A name for the input that is meaningful to the user. | 25 chars |     | input2.name |
| Interval | integer | The number of base intervals after which the input is sampled. A value of 1 means that the input is collected every base interval. Set to 0 to disable. | 0 to 10000 |     | input2.interval |
| Mode | preset | Specifies the function of the IN2 terminal. The calibration, warnings and alarms are applied to this mode. |     |     | input2.mode |
| **Digital 2** |     |     |     |     |     |
| Digital Threshold | decimal | A threshold against which the input is compared to determine if the input state is ON or OFF. | 0 to 30 | Volts | input2.digital.threshold |
| Digital Hysteresis | decimal | Once the input is in a certain state, hysteresis is the amount by which the input has to change before moving to the other state. | 0 to 20 | Volts | input2.digital.hysteresis |
| Count Hours | boolean | Counts the number of hours the digtial input is ON (above threshold). |     |     | input2.digital.count\_hours |
| Digital Change Alert | boolean | Sets whether a change in digital state generates an alert. |     |     | input2.digital.alert.enable |
| Analog 2 Calibration | text | Calibration parameters for Analog 2. Refer to user guide. | 30 chars |     | input2.cal |
| Unit | text | The unit of measure associated with the calibration. Examples: Litres/min, RPM, Volts |     |     | input2.unit |
| Warning | text | Warning thresholds. Refer to user guide. |     |     | input2.warning |
| Alarm | text | Alarm thresholds. Refer to user guide. |     |     | input2.alarm |
| Alarm/Warning Hysteresis | decimal | Once the input is in a certain state, hysteresis is the amount by which the input has to change before moving to the other state. |     |     | input2.hysteresis |
| **Output 1** |     |     |     |     |     |
| Name | text | A name for the input that is meaningful to the user. | 25 chars |     | output1.name |
| Interval | integer | Does not affect output mode. The number of base intervals at which the input is sampled. Set to 0 to disable. Set to 1 for every base interval. | 0 to 10000 |     | output1.interval |
| Mode | preset | Specifies the function of the OUT1 terminal. |     |     | output1.mode |
| Warnings | boolean | Determines if the output is turned on when a warning is active. |     |     | output1.warnings |
| Alarms | boolean | Determines if the output is turned on when an alarm is active. |     |     | output1.alarms |
| Alerts | boolean | Determines if the output is turned on when an alert is active. |     |     | output1.alerts |
| Hold Time | integer | Sets the time in seconds for which the output is held on after it is triggered. If set to zero, the output remains on while any exceptions are active. |     | Seconds | output1.hold\_time |
| Digital Change Alert | boolean | If enabled, a change in digital state will generate an alert. |     |     | output1.digital.alert.enable |
| Analog 3 Calibration | text | Calibration parameters for Analog 3. Refer to user guide. | 30 chars |     | output1.cal |
| Unit | text | The unit of measure associated with the calibration. Examples: Litres/min, RPM, Volts |     |     | output1.unit |
| Warning | text | Warning thresholds. Refer to user guide. |     |     | output1.warning |
| Alarm | text | Alarm thresholds. Refer to user guide. |     |     | output1.alarm |
| Alarm/Warning Hysteresis | decimal | Once the input is in a certain state, hysteresis is the amount by which the input has to change before moving to the other state. |     |     | output1.hysteresis |
| **Thermocouple 1** |     |     |     |     |     |
| Name | text | A name for the input that is meaningful to the user. | 25 chars |     | tc1.name |
| Interval | integer | The number of base intervals after which the thermocouple is measured and events are checked. A value of 1 means that the input is collected every base interval. Set to 0 to disable. | 0 to 10000 |     | tc1.interval |
| Hysteresis | decimal | The amount by which the measured value has to drop below the threshold to re-enable the event. | \-1000 to 1000 | &deg;C | tc1.hysteresis |
| Type | text | Determines the type of thermocouple connected. Valid values are: K, J, T, N, S, E, B and R | 1 chars |     | tc1.type |
| Warning | text | Warning thresholds. Refer to user guide. | \-1000 to 1000 | &deg;C | tc1.warning |
| Alarm | text | Alarm thresholds. Refer to user guide. | \-1000 to 1000 | &deg;C | tc1.alarm |
| **CAN 1** |     |     |     |     |     |
| Name | text | A name that is meaningful to the user. | 25 chars |     | can1.name |
| Interval | integer | The number of base intervals after which the CAN module is turned on. Set to 0 to disable. | 0 to 10000 |     | can1.interval |
| Nominal Baud Rate | integer | Baud rate for CAN communication. Supported values are: 125, 250, 500, 1000 |     | kbit/s | can1.nominal\_baud |
| Capture Time | integer | The device will capture matching messages for this length of time. |     | Seconds | can1.capture\_time |
| TX Enable | boolean | Allows the device to transmit and acknowledge messages on the CAN bus. |     |     | can1.tx\_enable |
| ID Capture List | text | List of IDs to be captured in HEX format, separated by a comma eg: 18FEE60A. Leave blank to capture all. | 200 chars |     | can1.id\_list |
| Send Raw Data | boolean | If ticked, all captured messages will be added to the data message. |     |     |     |
| **CAN 2** |     |     | 25 chars |     | can2.name |
| Name | text | A name that is meaningful to the user. | 0 to 10000 |     | can2.interval |
| Interval | integer | The number of base intervals after which the CAN module is turned on. Set to 0 to disable. |     | kbit/s | can2.nominal\_baud |
| Nominal Baud Rate | integer | Baud rate for CAN communication. Supported values are: 125, 250, 500, 1000 |     | Seconds | can2.capture\_time |
| Capture Time | integer | The device will capture matching messages for this length of time. |     |     | can2.tx\_enable |
| TX Enable | boolean | Allows the device to transmit and acknowledge messages on the CAN bus. | 200 chars |     | can2.id\_list |
| ID Capture List | text | List of IDs to be captured in HEX format, separated by a comma eg: 18FEE60A. Leave blank to capture all. |     |     |     |
| Send Raw Data | boolean | If ticked, all captured messages will be added to the data message. |     |     |     |
| **Current Loop 1** |     |     | 25 chars |     | current1.name |
| Name | text | A name for the input that is meaningful to the user. | 0 to 10000 |     | current1.interval |
| Interval | integer | The number of base intervals after which the input is sampled. A value of 1 means that the input is collected every base interval. Set to 0 to disable. |     |     | current1.mode |
| Mode | preset | Specifies the function of the SRC1 terminal. |     |     | current1.always\_on |
| Always On | boolean | Determines if Switched Power is to be enabled permanently. | 0 to 3600 | Seconds | current1.start\_time |
| Start Time | decimal | Time in seconds that the output is turned on before measurements are taken. Allows an external device to stabilise. |     |     | current1.digital.alert.enable |
| Digital Change Alert | boolean | Sets whether a change in digital state generates an alert. (Digital Mode Only) | 30 chars |     | current1.cal |
| Current 1 Calibration | text | Calibration parameters for Current 1. Refer to user guide. |     |     | current1.unit |
| Unit | text | The unit of measure associated with the calibration. Examples: Percent, Pascals, Meters |     |     | current1.warning |
| Warning | text | Warning thresholds. Refer to user guide. |     |     | current1.alarm |
| Alarm | text | Alarm thresholds. Refer to user guide. |     |     | current1.hysteresis |
| Alarm/Warning Hysteresis | decimal | The amount by which the calibrated current value has to drop below the threshold to re-enable the event. |     |     |     |
| **Current Loop 2** |     |     | 25 chars |     | current2.name |
| Name | text | A name for the input that is meaningful to the user. | 0 to 10000 |     | current2.interval |
| Interval | integer | The number of base intervals after which the input is sampled. A value of 1 means that the input is collected every base interval. Set to 0 to disable. |     |     | current2.mode |
| Mode | preset | Specifies the function of the SRC2 terminal. |     |     | current2.always\_on |
| Always On | boolean | Determines if Switched Power is to be enabled permanently. | 0 to 3600 | Seconds | current2.start\_time |
| Start Time | decimal | Time in seconds that the output is turned on before measurements are taken. Allows an external device to stabilise. |     |     | current2.digital.alert.enable |
| Digital Change Alert | boolean | Sets whether a change in digital state generates an alert. (Digital Mode Only) | 30 chars |     | current2.cal |
| Current 2 Calibration | text | Calibration parameters for Current 2. Refer to user guide. |     |     | current2.unit |
| Unit | text | The unit of measure associated with the calibration. Examples: Percent, Pascals, Meters |     |     | current2.warning |
| Warning | text | Warning thresholds. Refer to user guide. |     |     | current2.alarm |
| Alarm | text | Alarm thresholds. Refer to user guide. |     |     | current2.hysteresis |
| Alarm/Warning Hysteresis | decimal | The amount by which the calibrated current value has to drop below the threshold to re-enable the event. |     |     |     |
| **Serial 1** |     |     | 25 chars |     | serial1.name |
| Name | text | A name for the input that is meaningful to the user. | 0 to 10000 |     | serial1.interval |
| Interval | integer | The number of base intervals after which the serial port is turned on. Set to 0 to disable. |     |     | serial1.type |
| Type | preset | The electrical interface type. |     |     | serial1.termination |
| Termination Resistor | boolean | This parameter enables the integrated termination resistor. |     |     | serial1.mode |
| Mode | preset | Describes how the serial port is to be handled. CAPTURE: serial data is captured between start and end characters. MODBUS: serial data is treated according to MODBUS RTU standard |     |     | serial1.baud |
| Baud Rate | integer | Baud rate for serial communication. Common values are: 4800, 9600, 19200, 38400, 57600, 115200 |     |     | serial1.settings |
| Settings | text | A string describing the number of bytes: 7,8,9. Parity type: N(none), E(even), O(odd). Number of stop bits: 1 or 2. Typically: 8N1 |     |     |     |
| **Capture** |     |     | 32 chars |     | serial1.capture.start |
| Start String | text | The serial port starts reading data when it detects these characters. Example: $GPGGA, serial data will be ignored until $GPGGA is received after which data will be captured. If nothing is specified, the serial port will capture all data until the timeout period is reached. | 0 to 60000 | Milliseconds | serial1.capture.start\_idle\_time |
| Idle Time Before Start | integer | For a valid start condition, there must be this amount of idle time before receiving serial data. Additionally, the captured data will restarted if the serial port is idle for this time. Set to 0 to disable. | 32 chars |     | serial1.capture.end |
| End String | text | Once capturing, if these characters are received, the serial port will stop capturing and will return to sleep. For binary data or escape sequences refer to the User Guide. | 32 chars |     | serial1.capture.request |
| Request String | text | This string will be sent when the serial port is first turned on. Use this function to request data from a remote module. |     | Seconds | serial1.capture.maxtime |
| Max Time | integer | The device will wait this length of time for a valid capture. |     |     | serial1.capture.maxchars |
| Max Chars | integer | Maximum number of characters to be captured before the serial port goes back to sleep. |     |     | serial1.capture.alert |
| Alert on Capture | boolean | If checked an alert will be raised on any successful serial capture. |     |     |     |
| **MODBUS RTU** |     |     | 0 to 10 | Seconds | serial1.modbus.timeout |
| Slave Timeout | decimal | How long to wait for a response from each slave device. |     |     |     |
| **MODBUS 1** |     |     | 25 chars |     | mod1.name |
| Modbus 1 Name | text | A meaningful name for Modbus Channel 1. | 18 chars |     | mod1.settings |
| Modbus 1 Settings | text | Settings for Modbus Channel 1. Refer to user guide. | 30 chars |     | mod1.cal |
| Modbus 1 Calibration | text | Calibration paramters for Modbus Channel 1. Refer to user guide. |     |     | mod1.unit |
| Modbus 1 Unit | text | The unit of measure associated with the calibration. Examples: Percent, L/hr, Meters |     |     | mod1.warning |
| Warning | text | Warning thresholds. Refer to user guide. |     |     | mod1.alarm |
| Alarm | text | Alarm thresholds. Refer to user guide. |     |     |     |
| **MODBUS 2** |     |     | 25 chars |     | mod2.name |
| Modbus 2 Name | text | A meaningful name for Modbus Channel 2. | 18 chars |     | mod2.settings |
| Modbus 2 Settings | text | Settings for Modbus Channel 2. Refer to user guide. | 30 chars |     | mod2.cal |
| Modbus 2 Calibration | text | Calibration paramters for Modbus Channel 2. Refer to user guide. |     |     | mod2.unit |
| Modbus 2 Unit | text | The unit of measure associated with the calibration. Examples: Percent, L/hr, Meters |     |     | mod2.warning |
| Warning | text | Warning thresholds. Refer to user guide. |     |     | mod2.alarm |
| Alarm | text | Alarm thresholds. Refer to user guide. |     |     |     |
| **MODBUS 3** |     |     | 25 chars |     | mod3.name |
| Modbus 3 Name | text | A meaningful name for Modbus Channel 3. | 18 chars |     | mod3.settings |
| Modbus 3 Settings | text | Settings for Modbus Channel 3. Refer to user guide. | 30 chars |     | mod3.cal |
| Modbus 3 Calibration | text | Calibration paramters for Modbus Channel 3. Refer to user guide. |     |     | mod3.unit |
| Modbus 3 Unit | text | The unit of measure associated with the calibration. Examples: Percent, L/hr, Meters |     |     | mod3.warning |
| Warning | text | Warning thresholds. Refer to user guide. |     |     | mod3.alarm |
| Alarm | text | Alarm thresholds. Refer to user guide. |     |     |     |
| **MODBUS 4** |     |     | 25 chars |     | mod4.name |
| Modbus 4 Name | text | A meaningful name for Modbus Channel 4. | 18 chars |     | mod4.settings |
| Modbus 4 Settings | text | Settings for Modbus Channel 4. Refer to user guide. | 30 chars |     | mod4.cal |
| Modbus 4 Calibration | text | Calibration paramters for Modbus Channel 4. Refer to user guide. |     |     | mod4.unit |
| Modbus 4 Unit | text | The unit of measure associated with the calibration. Examples: Percent, L/hr, Meters |     |     | mod4.warning |
| Warning | text | Warning thresholds. Refer to user guide. |     |     | mod4.alarm |
| Alarm | text | Alarm thresholds. Refer to user guide. |     |     |     |
| **MODBUS 5** |     |     | 25 chars |     | mod5.name |
| Modbus 5 Name | text | A meaningful name for Modbus Channel 5. | 18 chars |     | mod5.settings |
| Modbus 5 Settings | text | Settings for Modbus Channel 5. Refer to user guide. | 30 chars |     | mod5.cal |
| Modbus 5 Calibration | text | Calibration paramters for Modbus Channel 5. Refer to user guide. |     |     | mod5.unit |
| Modbus 5 Unit | text | The unit of measure associated with the calibration. Examples: Percent, L/hr, Meters |     |     | mod5.warning |
| Warning | text | Warning thresholds. Refer to user guide. |     |     | mod5.alarm |
| Alarm | text | Alarm thresholds. Refer to user guide. |     |     |     |
| **MODBUS 6** |     |     | 18 chars |     | mod6.settings |
| Modbus 6 Settings | text | Settings for Modbus Channel 6. Refer to user guide. | 30 chars |     | mod6.cal |
| Modbus 6 Calibration | text | Calibration paramters for Modbus Channel 6. Refer to user guide. |     |     |     |
| **MODBUS 7** |     |     | 18 chars |     | mod7.settings |
| Modbus 7 Settings | text | Settings for Modbus Channel 7. Refer to user guide. | 30 chars |     | mod7.cal |
| Modbus 7 Calibration | text | Calibration paramters for Modbus Channel 7. Refer to user guide. |     |     |     |
| **MODBUS 8** |     |     | 18 chars |     | mod8.settings |
| Modbus 8 Settings | text | Settings for Modbus Channel 8. Refer to user guide. | 30 chars |     | mod8.cal |
| Modbus 8 Calibration | text | Calibration paramters for Modbus Channel 8. Refer to user guide. |     |     |     |
| **MODBUS 9** |     |     | 18 chars |     | mod9.settings |
| Modbus 9 Settings | text | Settings for Modbus Channel 9. Refer to user guide. | 30 chars |     | mod9.cal |
| Modbus 9 Calibration | text | Calibration paramters for Modbus Channel 9. Refer to user guide. |     |     |     |
| **MODBUS 10** |     |     | 18 chars |     | mod10.settings |
| Modbus 10 Settings | text | Settings for Modbus Channel 10. Refer to user guide. | 30 chars |     | mod10.cal |
| Modbus 10 Calibration | text | Calibration paramters for Modbus Channel 10. Refer to user guide. |     |     |     |
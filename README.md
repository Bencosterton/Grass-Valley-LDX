# Grass Valley LDK Gateway Tally Control

This repository contains a simple implementation for controlling tally lights on Grass Valley LDK Gateway camera systems using XML commands.

## Overview

The Grass Valley LDK Gateway uses an XML-based protocol for communication. 
Steps;

1. Authenticate with the gateway
2. Send tally control commands using the same socket connection

## XML Protocol Details

### Authentication

Before sending any tally commands, authentication is required:

**Authentication Request:**
```xml
<?xml version="2.0" encoding="UTF-8"?>
<application-authentication-request xml-protocol="2.0">
  <name>TallySender</name>
</application-authentication-request>
```

**Authentication Response:**
```xml
<request-response result="Ok" />
<application-authentication-indication xml-protocol="2.0">
  <supported-xml-protocol>1.1</supported-xml-protocol>
  <supported-xml-protocol>2.0</supported-xml-protocol>
  <name>SYSTEM-NAME</name>
  <location>SYSTEM-LOCATION</location>
</application-authentication-indication>
```

### Tally Control Commands

After successful authentication, tally control commands can be sent using the same socket connection:

**Turn Red Tally ON:**
```xml
<?xml version="2.0" encoding="UTF-8"?>
<function-value-change>
  <device>
    <sessionid>9VDA4O</sessionid>
    <function id="8215">
      <Value>1</Value>
    </function>
  </device>
</function-value-change>
```

**Turn Red Tally OFF:**
```xml
<?xml version="2.0" encoding="UTF-8"?>
<function-value-change>
  <device>
    <sessionid>9VDA4O</sessionid>
    <function id="8215">
      <Value>0</Value>
    </function>
  </device>
</function-value-change>
```

Alsoit could be useful to check the status of a tally, maybe?:

**Is Red Tally ON:**
```xml
<?xml version="2.0" encoding="UTF-8"?>
<function-value-request>
  <device>
	<deviceid>XCU-09</deviceid>
	<function id="8215">
	</function>
  </device>
</function-value-request>
```

**Response:**
```xml
<request-response result="Ok" />
<function-value-indication>
  <device>
	<sessionid>9VDA4O</sessionid>
	<name>9</name>
	<alias>ST1-CAM9</alias>
	<deviceid>XCU-09</deviceid>
	<type>Basestation</type>
	<function id="8215" blocked="false">
  	<value>0</value>
	</function>
  </device>
</function-value-indication>
```


## Function IDs

Some useful functino IDs

- **Red Tally**: 8215
- **Green Tally**: 8265
- **Yellow Tally**: 8234
- **Enable colour bars**: 795
- **Blue Gain**: 515
- **Green Gain**: 514
- **Red Gain**: 513
- **Auto-Black**: 820
- **Auto-Iris**: 784

## Implementation Details

1. **XML Version**: Use XML version 2.0 in the declaration
2. **Session ID**: The session ID (9VDA4O in examples) identifies the specific tally red identifier for a specific camera/device (I think)
3. **Socket Connection**: Maintain the same socket connection between authentication and tally commands

## Usage

```bash
# Turn red tally ON for camera XCU-09
python gv_tally_control.py --ip {GATEWAY-IP} --xcu XCU-09 --red on

# Turn red tally OFF for camera XCU-09
python gv_tally_control.py --ip {GATEWAY-IP} --xcu XCU-09 --red off
```


#include <Audio.h>
#include <Wire.h>
#include <SPI.h>
#include <SD.h>
#include <SerialFlash.h>
#include <SparkFun_WM8960_Arduino_Library.h>

AudioInputI2S i2s1;      //xy=764,265
AudioInputUSB usb2;      //xy=803.3333282470703,377.6666615009308
AudioOutputUSB usb1;     //xy=1009,263
AudioAnalyzePeak peak1;  //xy=1009.3333892822266,431.66669273376465
AudioOutputI2S2 i2s2;     // I2S output to codec
AudioConnection patchCord1(i2s1, 0, usb1, 0);
AudioConnection patchCord2(i2s1, 1, usb1, 1);
AudioConnection patchCord3(usb1, 0, i2s2, 0); //changed usb2 to usb 1 for loopback
AudioConnection patchCord4(usb1, 0, peak1, 0);//changed usb2 to usb 1 for loopback
AudioConnection patchCord5(usb1, 1, i2s2, 1);//changed usb2 to usb 1 for loopback
AudioConnection patchCord6(usb1, 1, peak1, 0);//changed usb2 to usb 1 for loopback

const int BodyMotorINA = 4;
const int BodyMotorINB = 5;
const int BodyMotorEnable = 7;
const int MouthMotor = 6;
const int MouthMotorEnable = 9;

bool MouthDirFlag = false;          // false = closing, true = opening
bool BodyDirFlag = false;           // false = closing, true = opening
unsigned long motorInterval = 100;  // default interval
elapsedMillis motorTimer;
elapsedMillis tailTimer;

WM8960 codec;
#define WM8960_ADDR 0x1A


void setup() {
  Wire.begin();
  Serial.begin(9600);
  Serial.println("USB Audio to WM8960 Headphone Output");
  if (!codec.begin()) {
    Serial.println("Codec not detected. Check wiring.");
    while (1);
  }
  codec_setup();  // Initializes codec and routing

  AudioMemory(40);
  pinMode(BodyMotorINA, OUTPUT);
  pinMode(BodyMotorINB, OUTPUT);
  pinMode(BodyMotorEnable, OUTPUT);
  pinMode(MouthMotor, OUTPUT);
  pinMode(MouthMotorEnable, OUTPUT);
}

void loop() {
  while(true){
  if (peak1.available()) {
    float amplitude = peak1.read();  // Range: 0.0 to 1.0
    if (amplitude > 0.01) {
      // Head Up
      digitalWrite(BodyMotorINB, HIGH);
      digitalWrite(BodyMotorINA, LOW);
      // Change direction based on timer
      if (motorTimer > motorInterval) {
        if (MouthDirFlag) {
          digitalWrite(MouthMotor, HIGH);
        } else {
          digitalWrite(MouthMotor, LOW);
        }
        MouthDirFlag = !MouthDirFlag;     // flip direction
        motorInterval = random(50, 500);  // randomize next interval (ms)
        motorTimer = 0;
      }
      continue;
    } 
  }
  if (tailTimer > 600) {
        if (BodyDirFlag) {
          Serial.println("tail up");
          digitalWrite(BodyMotorINB, LOW);
          digitalWrite(BodyMotorINA, HIGH);
        } else {
          Serial.println("tail down");
          digitalWrite(BodyMotorINB, LOW);
          digitalWrite(BodyMotorINA, LOW);
        }
        BodyDirFlag = !BodyDirFlag;
        tailTimer = 0;
      }
  }
}


// Write 9-bit I2C register to WM8960
void writeWM8960(uint8_t reg, uint16_t val) {
  Wire.beginTransmission(WM8960_ADDR);
  Wire.write((reg << 1) | ((val >> 8) & 0x01)); // 8-bit reg + 1-bit of val
  Wire.write(val & 0xFF);                      // 8-bit val
  Wire.endTransmission();
}


void codec_setup()
{
      // General setup needed
  codec.enableVREF();
  codec.enableVMID();

  // Setup signal flow to the ADC

  codec.enableLMIC();
  codec.enableRMIC();
  
  // Connect from INPUT1 to "n" (aka inverting) inputs of PGAs.
  codec.connectLMN1();
  codec.connectRMN1();

  // Disable mutes on PGA inputs (aka INTPUT1)
  codec.disableLINMUTE();
  codec.disableRINMUTE();

  // Set input boosts to get inputs 1 to the boost mixers
  codec.setLMICBOOST(WM8960_MIC_BOOST_GAIN_0DB);
  codec.setRMICBOOST(WM8960_MIC_BOOST_GAIN_0DB);

  codec.connectLMIC2B();
  codec.connectRMIC2B();

  // Enable boost mixers
  codec.enableAINL();
  codec.enableAINR();

  // Disconnect LB2LO (booster to output mixer (analog bypass)
  // For this example, we are going to pass audio throught the ADC and DAC
  codec.disableLB2LO();
  codec.disableRB2RO();

  // Connect from DAC outputs to output mixer
  codec.enableLD2LO();
  codec.enableRD2RO();

  // Set gainstage between booster mixer and output mixer
  // For this loopback example, we are going to keep these as low as they go
  codec.setLB2LOVOL(WM8960_OUTPUT_MIXER_GAIN_NEG_21DB); 
  codec.setRB2ROVOL(WM8960_OUTPUT_MIXER_GAIN_NEG_21DB);

  // Enable output mixers
  codec.enableLOMIX();
  codec.enableROMIX();

  // CLOCK STUFF, These settings will get you 44.1KHz sample rate, and class-d 
  // freq at 705.6kHz
  codec.enablePLL(); // Needed for class-d amp clock
  codec.setPLLPRESCALE(WM8960_PLLPRESCALE_DIV_2);
  codec.setSMD(WM8960_PLL_MODE_FRACTIONAL);
  codec.setCLKSEL(WM8960_CLKSEL_PLL);
  codec.setSYSCLKDIV(WM8960_SYSCLK_DIV_BY_2);
  codec.setBCLKDIV(4);
  codec.setDCLKDIV(WM8960_DCLKDIV_16);
  codec.setPLLN(7);
  codec.setPLLK(0x86, 0xC2, 0x26); // PLLK=86C226h	
  //codec.setADCDIV(0); // Default is 000 (what we need for 44.1KHz)
  //codec.setDACDIV(0); // Default is 000 (what we need for 44.1KHz)

  codec.enablePeripheralMode(); 
 // codec.setALRCGPIO(); // Note, should not be changed while ADC is enabled.

  // Enable ADCs and DACs
  codec.enableAdcLeft();
  codec.enableAdcRight();
  codec.enableDacLeft();
  codec.enableDacRight();
  codec.disableDacMute();

  //codec.enableLoopBack(); // Loopback sends ADC data directly into DAC

  codec.enableHeadphones();
  codec.enableOUT3MIX(); // Provides VMID as buffer for headphone ground

  Serial.println("Headphopne Amp Volume set to +0dB");
  codec.setHeadphoneVolumeDB(0.00);

  Serial.println("Codec setup complete. Listen to left/right INPUT1 on Headphone outputs.");
}
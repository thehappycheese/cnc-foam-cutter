/*
 * Arduino Pro Mini with MAX3232 Serial Communication + PWM Reading
 *
 * Connections:
 * Arduino Pro Mini -> MAX3232 Breakout
 * Pin 0 (RX)       -> TX (TTL side of MAX3232) - Programming/Hardware Serial
 * Pin 1 (TX)       -> RX (TTL side of MAX3232) - Programming/Hardware Serial
 * Pin 2 (Digital)  -> PWM Signal Input (1000Hz, 10%-90% duty cycle) - Hardware Interrupt
 * VCC              -> VCC (3.3V or 5V depending on your Pro Mini)
 * GND              -> GND
 *
 * MAX3232 Breakout -> Serial Connector (DB9 or similar)
 * T1OUT            -> Pin 3 (TX) of serial connector
 * R1IN             -> Pin 2 (RX) of serial connector
 * GND              -> Pin 5 (GND) of serial connector
 *
 * PWM Signal: Connect to Pin 2 (uses hardware interrupt)
 * - 1000Hz frequency
 * - 10%-90% duty cycle for normal operation
 * - <10% = outputs "0"
 * - >90% = outputs "100"
 * - 10%-90% = smooth interpolation from 0 to 100, then rounded to nearest 2%
 *
 * Serial Settings: 9600 baud, 8N1
 * NOTE: Programming serial is shared with hardware serial used for MAX3232
 */

// PWM reading pin (must be pin 2 for hardware interrupt)
const int PWM_READ_PIN = 2;

// Power supply control constants
const float MIN_CURRENT = 0.5;       // Minimum current in Amps
const float MAX_CURRENT = 4.0;       // Maximum current in Amps
const float VOLTAGE_SETTING = 20.0;  // Fixed voltage setting

// Timing variables
unsigned long previousDwelReportMillis = 0;
const long STATE_DWEL_REPEAT_INTERVAL = 1000;
const long COMMAND_INTERVAL = 50;         // 50ms minimum between commands

// Improved PWM measurement variables
volatile unsigned long pulseStartTime = 0;
volatile unsigned long pulseWidth = 0;
volatile unsigned long periodStart = 0;
volatile unsigned long period = 0;
volatile bool newPulseData = false;

// Sampling and averaging variables
const int NUM_SAMPLES = 10;
float duty_cycle_samples[NUM_SAMPLES];
int sampleIndex = 0;
unsigned long lastSampleTime = 0;
const long SAMPLE_INTERVAL = 2;  // ~2ms between samples for 10ms total
bool samplesReady = false;

// Output control variables
int output_level = 0;  // Initialize to -1 to force initial state setup
bool powerSupplyOn = false;

// Command queue structure
enum CommandType {
  CMD_OUTPUT_ON,
  CMD_OUTPUT_OFF,
  CMD_SET_VOLTAGE,
  CMD_SET_CURRENT
};

struct Command {
  CommandType type;
  float value;  // Used for voltage/current values
};

// Queue implementation
const int QUEUE_SIZE = 5;
Command commandQueue[QUEUE_SIZE];
int queueHead = 0;
int queueTail = 0;
int queueCount = 0;
unsigned long lastCommandTime = 0;

// Queue management functions
bool queueIsEmpty() {
  return queueCount == 0;
}

bool queueIsFull() {
  return queueCount >= QUEUE_SIZE;
}

bool enqueueCommand(CommandType type, float value = 0.0) {
  // Check if new value is different from the most recent value in queue
  if (!queueIsEmpty()) {
    // Get the most recent value (last enqueued)
    int lastIndex = (queueTail - 1 + QUEUE_SIZE) % QUEUE_SIZE;
    if (commandQueue[lastIndex].type == type && commandQueue[lastIndex].value == value) {
      return false;  // Duplicate value, don't enqueue
    }
  }
  
  if (queueIsFull()) {
    // Overwrite the last-in value instead of rejecting
    int lastIndex = (queueTail - 1 + QUEUE_SIZE) % QUEUE_SIZE;
    commandQueue[lastIndex].type = type;
    commandQueue[lastIndex].value = value;
    return true;
  }
  
  // Normal enqueue when queue is not full
  commandQueue[queueTail].type = type;
  commandQueue[queueTail].value = value;
  queueTail = (queueTail + 1) % QUEUE_SIZE;
  queueCount++;
  return true;
}

bool dequeueCommand(Command* cmd) {
  if (queueIsEmpty()) {
    return false;  // Queue is empty
  }
  
  *cmd = commandQueue[queueHead];
  queueHead = (queueHead + 1) % QUEUE_SIZE;
  queueCount--;
  return true;
}

// Function to execute a command
void executeCommand(const Command& cmd) {
  switch (cmd.type) {
    case CMD_OUTPUT_ON:
      Serial.println("OUT1");
      powerSupplyOn = true;
      break;
    case CMD_OUTPUT_OFF:
      Serial.println("OUT0");
      powerSupplyOn = false;
      break;
    case CMD_SET_VOLTAGE:
      Serial.print("VSET1:");
      Serial.println(cmd.value);
      break;
    case CMD_SET_CURRENT:
      Serial.print("ISET1:");
      Serial.println(cmd.value);
      break;
  }
}



// Interrupt service routine for PWM measurement
void pwmISR() {
  static unsigned long lastRisingEdge = 0;
  unsigned long currentTime = micros();

  if (digitalRead(PWM_READ_PIN) == HIGH) {
    // Rising edge - start of pulse
    pulseStartTime = currentTime;
    
    // Calculate period from last rising edge
    if (lastRisingEdge > 0) {
      period = currentTime - lastRisingEdge;
    }
    lastRisingEdge = currentTime;
  } else {
    // Falling edge - end of pulse
    if (pulseStartTime > 0) {
      pulseWidth = currentTime - pulseStartTime;
      newPulseData = true;
    }
  }
}

// Function to get current duty cycle reading with race condition protection
float get_current_duty_cycle() {
  // Disable interrupts briefly to get consistent readings
  noInterrupts();
  bool hasNewData = newPulseData;
  unsigned long currentPulseWidth = pulseWidth;
  unsigned long currentPeriod = period;
  newPulseData = false;  // Clear the flag
  interrupts();

  if (hasNewData && currentPeriod > 0) {
    // Use float math to avoid overflow
    float dutyCycle = (float(currentPulseWidth) * 100.0) / float(currentPeriod);
    if (dutyCycle<0.0){
      return 0.0;
    }
    if(dutyCycle>100.0){
      return 100.0;
    }
    return dutyCycle;
  }
  
  return 0.0;
}

// Updated function to handle invalid readings
float calculate_output_level_from_pwm_percentage(float duty_cycle_percent) {  
  float result;
  if (duty_cycle_percent < 10.0) {
    result = 0.0;
  } else if (duty_cycle_percent > 90.0) {
    result = 100.0;
  } else {
    // Smooth interpolation: map 10-90% to 0-100%
    result = ((duty_cycle_percent - 10.0) * 100.0) / 80.0;
  }
  return result;
}



void setup() {
  // 1 second delay before serial initialization to prevent soft-lock during programming
  delay(1000);

  // Initialize hardware serial for MAX3232 communication and programming
  Serial.begin(9600);

  // Setup PWM input pin
  pinMode(PWM_READ_PIN, INPUT);

  // Attach interrupt for PWM measurement (both rising and falling edges)
  // Pin 2 supports hardware interrupts
  attachInterrupt(digitalPinToInterrupt(PWM_READ_PIN), pwmISR, CHANGE);

  // Initialize sample array
  for (int i = 0; i < NUM_SAMPLES; i++) {
    duty_cycle_samples[i] = 0;
  }
}

void loop() {
  unsigned long currentMillis = millis();

  // Process command queue - execute one command every 50ms
  if (!queueIsEmpty() && (currentMillis - lastCommandTime >= COMMAND_INTERVAL)) {
    Command cmd;
    if (dequeueCommand(&cmd)) {
      executeCommand(cmd);
      lastCommandTime = currentMillis;
    }
  }

  // Sample PWM signal every ~2ms for averaging
  if (currentMillis - lastSampleTime >= SAMPLE_INTERVAL) {
    lastSampleTime = currentMillis;

    int currentDutyCycle = get_current_duty_cycle();

    // Store the sample
    duty_cycle_samples[sampleIndex] = currentDutyCycle;
    sampleIndex = (sampleIndex + 1) % NUM_SAMPLES;

    // Check if we have enough samples
    static int sampleCount = 0;
    if (sampleCount < NUM_SAMPLES) {
      sampleCount++;
    } else {
      samplesReady = true;
    }
  }

  // Process samples and queue commands when output changes
  if (samplesReady) {
    // Calculate average of samples
    float sum = 0;
    for (int i = 0; i < NUM_SAMPLES; i++) {
      sum += duty_cycle_samples[i];
    }
    float duty_cycle_average = sum / NUM_SAMPLES;
    float duty_cycle_rounded = ((int)(duty_cycle_average/2.0+0.5))*2.0;

    float output_level_new = calculate_output_level_from_pwm_percentage(duty_cycle_rounded);
    bool dwel_time_expired  = currentMillis - previousDwelReportMillis >= STATE_DWEL_REPEAT_INTERVAL;
    bool significant_change = abs(output_level_new - output_level)>2.0;
    // Queue a repeat of the current state every 1 second regardless of change
    if (
         dwel_time_expired
      || significant_change
    ) {
      previousDwelReportMillis = currentMillis;
      output_level = output_level_new;
      if (output_level == 0) {
        enqueueCommand(CMD_OUTPUT_OFF);
        enqueueCommand(CMD_SET_VOLTAGE, VOLTAGE_SETTING);
      } else {
        if (dwel_time_expired) {
          enqueueCommand(CMD_OUTPUT_ON);
        }
        float currentSetting = (MAX_CURRENT - MIN_CURRENT) * (output_level / 100.0) + MIN_CURRENT;
        enqueueCommand(CMD_SET_CURRENT, currentSetting);
      }
    }

  }
  
}
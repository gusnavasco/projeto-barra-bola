// Projeto Barra-Bola

#include <ESP32Servo.h>
#include <Wire.h>
#include <ModbusRTU.h>
#include "Adafruit_VL53L0X.h"

// --- Definições de Hardware e Comunicação ---
#define PIN_SDA 21
#define PIN_SCL 23
#define PIN_SERVO 13
#define SLAVE_ID 1
#define BAUDRATE 9600

ModbusRTU mb;

// --- Objetos ---
Adafruit_VL53L0X lox = Adafruit_VL53L0X();
Servo myservo;
int servo_angle = 0;

// --- Controle de Estado ---
bool is_active = true;
enum controller_choice {
  NOT_SELECTED = 0,
  PID = 1,
  PHASE_LEAD = 2 
};
uint16_t active_controller = NOT_SELECTED;

// --- Variáveis dos Controladores ---
double controller_output = 0.0;
double previous_controller_output = 0.0;
double setpoint = 20.0;
double error = 0.0;
double previous_error = 0.0;

// Parâmetros PID
double Kp = 9.2;
double Ki = 6.2;
double Kd = 8.0; 
double cumulative_error = 0.0;
double error_rate = 0.0;
const double max_cumulative_error = 90000.0;
const double min_cumulative_error = -90000.0;

// Parâmetros Avanço de Fase
double K = 1.0; 

// --- Sensor e Filtragem ---
double ball_distance_cm = 0.0;
double filtered_ball_distance = 0.0;
double alpha = 0.1; 

// --- Temporização ---
unsigned long current_time;
unsigned long previous_time;
double elapsed_time;

// --- Protótipos ---
double pid_controller(float error);
double phase_lead_controller(double current_error);
double sensor_correction_function(double measured_distance);
float measure_ball_distance();
void limit_servo_angle(void);

void setup() {
  Serial.begin(BAUDRATE, SERIAL_8N1);
  mb.begin(&Serial);
  mb.slave(SLAVE_ID); 

  // --- Registradores Modbus ---
  mb.addCoil(0);  // Leitura/Escrita - Flag On/Off
  mb.addHreg(0);  // Escrita - Setpoint
  mb.addHreg(1);  // Escrita - Método de Controle (1=PID, 2=Avanço)
  mb.addIreg(0);  // Leitura - Posição da bola (escalado x100)
  mb.addIreg(1);  // Leitura - Saída do controlador (escalado x100)
  mb.addIreg(2);  // Leitura - Setpoint (escalado x100)
  mb.addHreg(2);  // Escrita - Ganho Kp
  mb.addHreg(3);  // Escrita - Ganho Ki
  mb.addHreg(4);  // Escrita - Ganho Kd
  mb.addHreg(5);  // Escrita - Ganho K do Avanço
 
  Wire.begin(PIN_SDA, PIN_SCL);
  if (!lox.begin()) {
    Serial.println(F("Failed to boot VL53L0X"));
    while (1);
  }
  
  myservo.attach(PIN_SERVO);
  
  // Leitura inicial para estabilizar filtro
  filtered_ball_distance = measure_ball_distance();
  previous_time = millis();
}

void loop() {
  mb.task(); 
  
  is_active = mb.Coil(0);

  if (is_active) {
    active_controller = mb.Hreg(1);
    setpoint = mb.Hreg(0) / 100.0;
    
    // Filtro passa-baixa (suavização exponencial simples)
    filtered_ball_distance = (alpha * measure_ball_distance()) + ((1.0 - alpha) * filtered_ball_distance);
   
    error = setpoint - filtered_ball_distance;
     
    switch (active_controller) {
      case NOT_SELECTED:
        servo_angle = 84; // Posição de equilíbrio da barra
        controller_output = 0;

        // Reseta estados para suavizar transição
        cumulative_error = 0; 
        previous_error = error; 
        previous_time = millis();
        previous_controller_output = 0; 
        break;
    
      case PID:
        Kp = mb.Hreg(2) / 100.0;
        Ki = mb.Hreg(3) / 100.0;
        Kd = mb.Hreg(4) / 100.0;
        
        controller_output = pid_controller(error);
        servo_angle = (int)controller_output + 115; // +115 offset PID
        break;
     
      case PHASE_LEAD:
        K = mb.Hreg(5) / 100.0;
        
        controller_output = phase_lead_controller(error);
        servo_angle = (int)controller_output + 89; // +89 offset Avanço
        break;
    }
   
    // Escala x100 para transmissão inteira no Modbus
    mb.Ireg(0, (uint16_t)(filtered_ball_distance * 100.0));
    mb.Ireg(1, (uint16_t)(controller_output * 100.0));
    mb.Ireg(2, (uint16_t)(setpoint * 100.0));
   
    limit_servo_angle(); 
    myservo.write(servo_angle);
  }
}

double pid_controller(float error) {
  current_time = millis();
  elapsed_time = current_time - previous_time;
  
  cumulative_error += error * elapsed_time;
  
  // Anti-windup
  if (cumulative_error > max_cumulative_error) {
    cumulative_error = max_cumulative_error;
  } else if (cumulative_error < min_cumulative_error) {
    cumulative_error = min_cumulative_error;
  }
  
  error_rate = (error - previous_error) / elapsed_time;
  
  // u(t) = (Kp * 0.1 * e) + (Ki * 0.0001 * int(e)) + (Kd * 100 * de/dt)
  controller_output = (Kp * 0.1 * error) + (Ki * 0.0001 * cumulative_error) + (Kd * 100 * error_rate); 
  
  previous_error = error;
  previous_time = current_time;
  return controller_output;
}

double phase_lead_controller(double current_error) {
  // u[k] = 0.7914*u[k-1] + 5.56*K*e[k] - 5.381*K*e[k-1]
  controller_output = (0.7914 * previous_controller_output) + (K * 5.56 * current_error) - (K * 5.381 * previous_error); 
  
  previous_controller_output = controller_output;
  previous_error = current_error;
  return controller_output;
}

double sensor_correction_function(double measured_distance) {
    // Polinômio de correção de 3º grau
    return 0.0004 * pow(measured_distance, 3) - 0.0262 * pow(measured_distance, 2) + 1.3680 * measured_distance - 2.5749;
}

float measure_ball_distance() {
  VL53L0X_RangingMeasurementData_t measure;
  lox.rangingTest(&measure, false);
  
  if (measure.RangeStatus != 4) {
    float ball_distance_mm = measure.RangeMilliMeter;
    ball_distance_cm = ball_distance_mm / 10;
  }
  
  return sensor_correction_function(ball_distance_cm);
}

void limit_servo_angle(void) {
  if (servo_angle > 120) {
    servo_angle = 120;
  }
  if (servo_angle < 60) {
    servo_angle = 60;
  }
}
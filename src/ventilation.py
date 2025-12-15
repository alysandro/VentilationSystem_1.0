import json
import logging
import threading
import time
from dataclasses import dataclass
from typing import Any, Dict

# Настройка логирования
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[logging.FileHandler("ventilation.log"), logging.StreamHandler()],
)
logger = logging.getLogger("Ventilation")


@dataclass
class SensorData:
    temperature: float
    humidity: float
    co2: float
    airflow: float


@dataclass
class SystemState:
    heating: bool = False
    cooling: bool = False
    humidifier: bool = False
    fan_speed: int = 0  # 0-100%
    recuperator: bool = False


class VentilationSystem:
    def __init__(self):
        self.settings = self.load_settings()
        self.state = SystemState()
        self.sensor_data = SensorData(0.0, 0.0, 0.0, 0.0)
        self.running = True
        self.simulate_sensors = True  # Имитация датчиков

    def load_settings(self) -> Dict[str, Any]:
        """Загрузка настроек из файла."""
        try:
            with open("settings.json", "r") as f:
                return json.load(f)
        except FileNotFoundError:
            return {
                "target_temp": 22.0,
                "target_humidity": 50.0,
                "co2_limit": 800,
                "min_airflow": 30.0,
                "recuperator_enabled": True,
            }

    def save_settings(self):
        """Сохранение настроек в файл."""
        with open("settings.json", "w") as f:
            json.dump(self.settings, f, indent=2)

    def read_sensors(self) -> SensorData:
        """Чтение данных с датчиков."""
        if self.simulate_sensors:
            import random

            return SensorData(
                temperature=20.0 + random.uniform(-2, 5),
                humidity=45.0 + random.uniform(-10, 10),
                co2=600 + random.randint(-100, 300),
                airflow=40.0 + random.uniform(-5, 10),
            )
        else:
            # Пока реальные датчики не реализованы — возвращаем заглушку
            logger.warning("Реальные датчики не подключены — используется заглушка")
            return SensorData(temperature=20.0, humidity=50.0, co2=400.0, airflow=40.0)

    def control_heating(self, temp: float):
        """Управление нагревателем."""
        target = self.settings["target_temp"]
        if temp < target - 1.0:
            self.state.heating = True
            logger.info(f"Нагреватель включён (T={temp:.1f}°C < {target:.1f}°C)")
        elif temp > target + 0.5:
            self.state.heating = False
            logger.info(f"Нагреватель выключен (T={temp:.1f}°C > {target:.1f}°C)")

    def control_cooling(self, temp: float):
        """Управление охлаждением."""
        max_temp = self.settings["target_temp"] + 3.0
        if temp > max_temp:
            self.state.cooling = True
            logger.info(f"Охлаждение включено (T={temp:.1f}°C > {max_temp:.1f}°C)")
        else:
            self.state.cooling = False

    def control_humidifier(self, humidity: float):
        """Управление увлажнителем."""
        target = self.settings["target_humidity"]
        if humidity < target - 5.0:
            self.state.humidifier = True
            logger.info(f"Увлажнитель включён (H={humidity:.1f}% < {target:.1f}%)")
        elif humidity > target + 3.0:
            self.state.humidifier = False
            logger.info(f"Увлажнитель выключен (H={humidity:.1f}% > {target:.1f}%)")

    def control_fan(self, co2: float, airflow: float):
        """Управление скоростью вентилятора."""
        co2_limit = self.settings["co2_limit"]
        min_airflow = self.settings["min_airflow"]

        if co2 > co2_limit or airflow < min_airflow:
            self.state.fan_speed = 100
            logger.info(
                f"Вентилятор на 100% (CO₂={co2:.0f}ppm или airflow={airflow:.1f})"
            )
        else:
            self.state.fan_speed = 50
            logger.info("Вентилятор на 50% (нормальные параметры)")

    def control_recuperator(self, temp: float):
        """Управление рекуператором."""
        if self.settings["recuperator_enabled"] and temp > 5.0:
            self.state.recuperator = True
        else:
            self.state.recuperator = False

    def update_system(self):
        """Основной алгоритм управления."""
        self.sensor_data = self.read_sensors()
        temp = self.sensor_data.temperature
        humidity = self.sensor_data.humidity
        co2 = self.sensor_data.co2
        airflow = self.sensor_data.airflow

        logger.info(
            f"Датчики: T={temp:.1f}°C, H={humidity:.1f}%, "
            f"CO₂={co2:.0f}ppm, airflow={airflow:.1f}"
        )

        self.control_heating(temp)
        self.control_cooling(temp)
        self.control_humidifier(humidity)
        self.control_fan(co2, airflow)
        self.control_recuperator(temp)

    from typing import TYPE_CHECKING

    if TYPE_CHECKING:
        from flask import Flask, Response

    def web_interface(self):
        """Простой веб-интерфейс (требуется Flask)."""
        try:
            from flask import Flask, jsonify, request

            app = Flask(__name__)

            @app.route("/status", methods=["GET"])
            def get_status():
                return jsonify(
                    {
                        "sensor_data": self.sensor_data.__dict__,
                        "state": self.state.__dict__,
                        "settings": self.settings,
                    }
                )

            @app.route("/settings", methods=["POST"])
            def update_settings():
                data = request.json
                self.settings.update(data)
                self.save_settings()
                return jsonify({"status": "ok"})

            logger.info("Веб-интерфейс запущен на http://localhost:5000")
            app.run(host="0.0.0.0", port=5000)
        except ImportError:
            logger.warning("Flask не установлен. Веб-интерфейс недоступен.")

    def run(self):
        """Основной цикл работы."""
        logger.info("Система вентиляции запущена")

        web_thread = threading.Thread(target=self.web_interface, daemon=True)
        web_thread.start()

        try:
            while self.running:
                self.update_system()
                time.sleep(10)  # Цикл каждые 10 секунд
        except KeyboardInterrupt:
            logger.info("Остановка системы по запросу пользователя")
        finally:
            self.cleanup()

    def cleanup(self):
        """Очистка при завершении."""
        logger.info("Выключение всех устройств")
        self.state = SystemState()  # Все устройства выключены


if __name__ == "__main__":
    system = VentilationSystem()
    system.run()

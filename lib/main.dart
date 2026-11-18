import 'dart:async';
import 'package:flutter/material.dart';
import 'package:flutter_background_service/flutter_background_service.dart';
import 'package:battery_plus/battery_plus.dart';
import 'package:flutter_local_notifications/flutter_local_notifications.dart';
import 'package:http/http.dart' as http;

// !!! ВПИШИ СЮДА IP ТВОЕГО КОМПА !!!
const String laptopIp = '192.168.1.107';

Future<void> main() async {
  WidgetsFlutterBinding.ensureInitialized();

  // Создаём канал уведомлений ДО запуска сервиса —
  // иначе сервис упадёт с "invalid channel" на Android 9
  final FlutterLocalNotificationsPlugin notifications =
  FlutterLocalNotificationsPlugin();

  await notifications
      .resolvePlatformSpecificImplementation<
      AndroidFlutterLocalNotificationsPlugin>()
      ?.createNotificationChannel(
    const AndroidNotificationChannel(
      'battery_alert_channel',
      'Battery Alert',
      importance: Importance.low,
    ),
  );

  final service = FlutterBackgroundService();

  await service.configure(
    androidConfiguration: AndroidConfiguration(
      onStart: onStart,
      isForegroundMode: true,
      autoStartOnBoot: true,
      notificationChannelId: 'battery_alert_channel',
      initialNotificationTitle: 'Battery Alert',
      initialNotificationContent: 'Слежу за зарядом батареи',
      foregroundServiceNotificationId: 1,
    ),
    iosConfiguration: IosConfiguration(),
  );

  service.startService();
}

// Эта функция живёт в фоновом процессе. Точка входа для сервиса.
@pragma('vm:entry-point')
Future<void> onStart(ServiceInstance service) async {
  final battery = Battery();

    Future<void> check() async {
    try {
      final level = await battery.batteryLevel;
      await http.post(
        Uri.parse('http://$laptopIp:8080/battery'),
        headers: {'Content-Type': 'application/json'},
        body: '{"level": $level}',
      );
    } catch (_) {
      // Сеть или сервер недоступны — повторим на следующем опросе
    }
  }


  await check();
  // Опрашиваем батарею раз в минуту — этого достаточно для задачи
  Timer.periodic(const Duration(minutes: 1), (_) => check());
}

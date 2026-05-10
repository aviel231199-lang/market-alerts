import 'dart:io' show Platform;
import 'package:firebase_messaging/firebase_messaging.dart';
import 'api.dart';

class FcmService {
  static Future<void> registerWithBackend() async {
    final fm = FirebaseMessaging.instance;
    await fm.requestPermission(alert: true, badge: true, sound: true);
    final token = await fm.getToken();
    if (token == null) return;
    final platform = Platform.isIOS ? 'ios' : 'android';
    try {
      await Api.registerDevice(token, platform);
    } catch (_) {}
    fm.onTokenRefresh.listen((t) => Api.registerDevice(t, platform));
  }
}

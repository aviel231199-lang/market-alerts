import 'package:firebase_core/firebase_core.dart';
import 'package:firebase_messaging/firebase_messaging.dart';
import 'package:flutter/material.dart';

import 'screens/login_screen.dart';
import 'screens/home_screen.dart';
import 'services/api.dart';
import 'services/auth_store.dart';
import 'services/fcm_service.dart';

Future<void> _bgHandler(RemoteMessage msg) async {
  // No-op; system tray displays notification automatically.
}

void main() async {
  WidgetsFlutterBinding.ensureInitialized();
  await Firebase.initializeApp();
  FirebaseMessaging.onBackgroundMessage(_bgHandler);
  runApp(const MarketAlertsApp());
}

class MarketAlertsApp extends StatelessWidget {
  const MarketAlertsApp({super.key});

  @override
  Widget build(BuildContext context) {
    return MaterialApp(
      title: 'Market Alerts',
      theme: ThemeData(colorSchemeSeed: Colors.indigo, useMaterial3: true),
      darkTheme: ThemeData(colorSchemeSeed: Colors.indigo, brightness: Brightness.dark, useMaterial3: true),
      home: const _Bootstrap(),
    );
  }
}

class _Bootstrap extends StatefulWidget {
  const _Bootstrap();
  @override
  State<_Bootstrap> createState() => _BootstrapState();
}

class _BootstrapState extends State<_Bootstrap> {
  Future<bool>? _ready;

  @override
  void initState() {
    super.initState();
    _ready = _init();
  }

  Future<bool> _init() async {
    final token = await AuthStore.token();
    if (token == null) return false;
    Api.setToken(token);
    await FcmService.registerWithBackend();
    return true;
  }

  @override
  Widget build(BuildContext context) {
    return FutureBuilder<bool>(
      future: _ready,
      builder: (ctx, snap) {
        if (!snap.hasData) {
          return const Scaffold(body: Center(child: CircularProgressIndicator()));
        }
        return snap.data! ? const HomeScreen() : const LoginScreen();
      },
    );
  }
}

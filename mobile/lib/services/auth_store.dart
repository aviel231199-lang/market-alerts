import 'package:shared_preferences/shared_preferences.dart';

class AuthStore {
  static const _k = 'jwt';

  static Future<String?> token() async {
    final p = await SharedPreferences.getInstance();
    return p.getString(_k);
  }

  static Future<void> save(String t) async {
    final p = await SharedPreferences.getInstance();
    await p.setString(_k, t);
  }

  static Future<void> clear() async {
    final p = await SharedPreferences.getInstance();
    await p.remove(_k);
  }
}

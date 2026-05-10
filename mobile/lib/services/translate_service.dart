import 'package:shared_preferences/shared_preferences.dart';
import 'api.dart';

class TranslateService {
  static const _prefKey = 'lang_hebrew';
  static bool _hebrewEnabled = false;
  static final _cache = <String, String>{};

  static bool get hebrewEnabled => _hebrewEnabled;

  static Future<void> load() async {
    final p = await SharedPreferences.getInstance();
    _hebrewEnabled = p.getBool(_prefKey) ?? false;
  }

  static Future<void> setHebrew(bool value) async {
    _hebrewEnabled = value;
    final p = await SharedPreferences.getInstance();
    await p.setBool(_prefKey, value);
    _cache.clear();
  }

  static Future<String> translate(String text) async {
    if (!_hebrewEnabled || text.isEmpty) return text;
    if (_cache.containsKey(text)) return _cache[text]!;
    try {
      final result = await Api.translateToHebrew(text);
      _cache[text] = result;
      return result;
    } catch (_) {
      return text;
    }
  }

  static Future<List<String>> translateBatch(List<String> texts) async {
    if (!_hebrewEnabled) return texts;
    try {
      return await Api.translateBatch(texts);
    } catch (_) {
      return texts;
    }
  }
}

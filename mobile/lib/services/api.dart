import 'dart:convert';
import 'package:http/http.dart' as http;

class Api {
  // In production set --dart-define=API_BASE=https://your-domain.com
  // The http://10.0.2.2 default is for Android emulator local dev only
  static String baseUrl = const String.fromEnvironment('API_BASE', defaultValue: 'http://10.0.2.2:8000');
  static String? _token;

  static void setToken(String? t) => _token = t;

  static Map<String, String> _headers({bool json = true}) => {
        if (json) 'Content-Type': 'application/json',
        if (_token != null) 'Authorization': 'Bearer $_token',
      };

  static Future<String> register(String email, String password, {required String inviteCode}) async {
    final r = await http.post(Uri.parse('$baseUrl/auth/register'),
        headers: _headers(),
        body: jsonEncode({'email': email, 'password': password, 'invite_code': inviteCode}));
    if (r.statusCode >= 400) throw Exception(r.body);
    return jsonDecode(r.body)['access_token'] as String;
  }

  static Future<String> login(String email, String password) async {
    final r = await http.post(Uri.parse('$baseUrl/auth/login'),
        headers: _headers(), body: jsonEncode({'email': email, 'password': password}));
    if (r.statusCode >= 400) throw Exception(r.body);
    return jsonDecode(r.body)['access_token'] as String;
  }

  static Future<void> registerDevice(String fcmToken, String platform) async {
    final r = await http.post(Uri.parse('$baseUrl/devices'),
        headers: _headers(), body: jsonEncode({'fcm_token': fcmToken, 'platform': platform}));
    if (r.statusCode >= 400) throw Exception(r.body);
  }

  static Future<List<dynamic>> getWatchlist() async {
    final r = await http.get(Uri.parse('$baseUrl/watchlist'), headers: _headers(json: false));
    if (r.statusCode >= 400) throw Exception(r.body);
    return jsonDecode(r.body) as List;
  }

  static Future<void> addWatch(String kind, String value) async {
    final r = await http.post(Uri.parse('$baseUrl/watchlist'),
        headers: _headers(), body: jsonEncode({'kind': kind, 'value': value}));
    if (r.statusCode >= 400) throw Exception(r.body);
  }

  static Future<void> deleteWatch(int id) async {
    final r = await http.delete(Uri.parse('$baseUrl/watchlist/$id'), headers: _headers(json: false));
    if (r.statusCode >= 400) throw Exception(r.body);
  }

  static Future<List<dynamic>> getNews() async {
    final r = await http.get(Uri.parse('$baseUrl/news?limit=100'), headers: _headers(json: false));
    if (r.statusCode >= 400) throw Exception(r.body);
    return jsonDecode(r.body) as List;
  }

  static Future<String> translateToHebrew(String text) async {
    final r = await http.post(Uri.parse('$baseUrl/analyze/translate'),
        headers: _headers(), body: jsonEncode({'text': text}));
    if (r.statusCode >= 400) throw Exception(r.body);
    return jsonDecode(r.body)['translation'] as String;
  }

  static Future<List<String>> translateBatch(List<String> texts) async {
    final r = await http.post(Uri.parse('$baseUrl/analyze/translate'),
        headers: _headers(), body: jsonEncode({'texts': texts}));
    if (r.statusCode >= 400) throw Exception(r.body);
    return (jsonDecode(r.body)['translations'] as List).cast<String>();
  }

  static Future<Map<String, dynamic>> analyzeReport(String ticker, {String formType = '10-Q'}) async {
    final r = await http.get(
        Uri.parse('$baseUrl/analyze/report/$ticker?form_type=$formType'),
        headers: _headers(json: false));
    if (r.statusCode >= 400) throw Exception(r.body);
    return jsonDecode(r.body) as Map<String, dynamic>;
  }
}

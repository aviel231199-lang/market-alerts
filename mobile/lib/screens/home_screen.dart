import 'package:flutter/material.dart';
import 'package:url_launcher/url_launcher.dart';

import '../services/api.dart';
import '../services/auth_store.dart';
import '../services/translate_service.dart';
import 'login_screen.dart';
import 'report_screen.dart';
import 'watchlist_screen.dart';

class HomeScreen extends StatefulWidget {
  const HomeScreen({super.key});
  @override
  State<HomeScreen> createState() => _HomeScreenState();
}

class _HomeScreenState extends State<HomeScreen> {
  late Future<List<dynamic>> _news;
  bool _hebrew = false;
  List<String>? _translatedTitles;

  @override
  void initState() {
    super.initState();
    _hebrew = TranslateService.hebrewEnabled;
    _news = _loadNews();
  }

  Future<List<dynamic>> _loadNews() async {
    final items = await Api.getNews();
    if (_hebrew && items.isNotEmpty) {
      final titles = items.map((n) => (n['title'] as String?) ?? '').toList();
      _translatedTitles = await TranslateService.translateBatch(titles);
    } else {
      _translatedTitles = null;
    }
    return items;
  }

  Future<void> _refresh() async {
    setState(() => _news = _loadNews());
    await _news;
  }

  Future<void> _toggleHebrew(bool val) async {
    await TranslateService.setHebrew(val);
    setState(() {
      _hebrew = val;
      _translatedTitles = null;
      _news = _loadNews();
    });
  }

  Future<void> _logout() async {
    await AuthStore.clear();
    Api.setToken(null);
    if (!mounted) return;
    Navigator.of(context).pushReplacement(MaterialPageRoute(builder: (_) => const LoginScreen()));
  }

  String _titleAt(int i, Map<String, dynamic> n) {
    if (_hebrew && _translatedTitles != null && i < _translatedTitles!.length) {
      return _translatedTitles![i];
    }
    return n['title'] ?? '';
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(
        title: const Text('Market Alerts'),
        actions: [
          // Hebrew toggle
          Tooltip(
            message: _hebrew ? 'עברית פעיל' : 'עבור לעברית',
            child: Row(children: [
              Text('🇮🇱', style: TextStyle(fontSize: 18, color: _hebrew ? Colors.white : Colors.white38)),
              Switch(value: _hebrew, onChanged: _toggleHebrew, activeColor: Colors.blue[200]),
            ]),
          ),
          // AI report analyzer
          IconButton(
            icon: const Text('🤖', style: TextStyle(fontSize: 20)),
            tooltip: 'ניתוח דוחות AI',
            onPressed: () => Navigator.of(context)
                .push(MaterialPageRoute(builder: (_) => const ReportScreen())),
          ),
          IconButton(
            icon: const Icon(Icons.bookmark),
            onPressed: () => Navigator.of(context)
                .push(MaterialPageRoute(builder: (_) => const WatchlistScreen())),
          ),
          IconButton(icon: const Icon(Icons.logout), onPressed: _logout),
        ],
      ),
      body: RefreshIndicator(
        onRefresh: _refresh,
        child: FutureBuilder<List<dynamic>>(
          future: _news,
          builder: (ctx, snap) {
            if (!snap.hasData && !snap.hasError) {
              return const Center(child: Column(
                mainAxisAlignment: MainAxisAlignment.center,
                children: [
                  CircularProgressIndicator(),
                  SizedBox(height: 12),
                  Text('טוען חדשות...', style: TextStyle(color: Colors.grey)),
                ],
              ));
            }
            if (snap.hasError) return Center(child: Text('שגיאה: ${snap.error}'));
            final items = snap.data!;
            if (items.isEmpty) {
              return const Center(child: Padding(
                padding: EdgeInsets.all(24),
                child: Text(
                  'אין חדשות עדיין.\nהוסף מניות ומילות מפתח ל-Watchlist שלך.',
                  textAlign: TextAlign.center,
                  style: TextStyle(color: Colors.grey),
                ),
              ));
            }
            return ListView.separated(
              itemCount: items.length,
              separatorBuilder: (_, __) => const Divider(height: 1),
              itemBuilder: (_, i) {
                final n = items[i] as Map<String, dynamic>;
                final tickers = (n['tickers'] as List?)?.join(', ') ?? '';
                final source = n['source'] as String? ?? '';
                return ListTile(
                  title: Text(_titleAt(i, n), style: const TextStyle(fontSize: 14)),
                  subtitle: Text(
                    '$source${tickers.isNotEmpty ? '  ·  $tickers' : ''}',
                    style: TextStyle(fontSize: 12, color: Colors.grey[600]),
                  ),
                  trailing: const Icon(Icons.open_in_new, size: 16),
                  onTap: () {
                    final url = n['url'] as String?;
                    if (url != null && url.isNotEmpty) {
                      launchUrl(Uri.parse(url), mode: LaunchMode.externalApplication);
                    }
                  },
                );
              },
            );
          },
        ),
      ),
    );
  }
}

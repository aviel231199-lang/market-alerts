import 'package:flutter/material.dart';
import 'package:url_launcher/url_launcher.dart';

import '../services/api.dart';
import '../services/auth_store.dart';
import 'login_screen.dart';
import 'watchlist_screen.dart';

class HomeScreen extends StatefulWidget {
  const HomeScreen({super.key});
  @override
  State<HomeScreen> createState() => _HomeScreenState();
}

class _HomeScreenState extends State<HomeScreen> {
  late Future<List<dynamic>> _news;

  @override
  void initState() {
    super.initState();
    _news = Api.getNews();
  }

  Future<void> _refresh() async {
    setState(() => _news = Api.getNews());
    await _news;
  }

  Future<void> _logout() async {
    await AuthStore.clear();
    Api.setToken(null);
    if (!mounted) return;
    Navigator.of(context).pushReplacement(MaterialPageRoute(builder: (_) => const LoginScreen()));
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(
        title: const Text('Market Alerts'),
        actions: [
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
            if (!snap.hasData) return const Center(child: CircularProgressIndicator());
            final items = snap.data!;
            if (items.isEmpty) {
              return const Center(child: Text('No news yet — add tickers/keywords to your watchlist.'));
            }
            return ListView.separated(
              itemCount: items.length,
              separatorBuilder: (_, __) => const Divider(height: 1),
              itemBuilder: (_, i) {
                final n = items[i] as Map<String, dynamic>;
                final tickers = (n['tickers'] as List?)?.join(', ') ?? '';
                return ListTile(
                  title: Text(n['title'] ?? ''),
                  subtitle: Text('${n['source']}  ·  $tickers'),
                  trailing: const Icon(Icons.open_in_new),
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

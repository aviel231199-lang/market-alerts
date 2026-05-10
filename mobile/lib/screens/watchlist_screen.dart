import 'package:flutter/material.dart';

import '../services/api.dart';

class WatchlistScreen extends StatefulWidget {
  const WatchlistScreen({super.key});
  @override
  State<WatchlistScreen> createState() => _WatchlistScreenState();
}

class _WatchlistScreenState extends State<WatchlistScreen> {
  late Future<List<dynamic>> _items;
  final _input = TextEditingController();
  String _kind = 'ticker';

  @override
  void initState() {
    super.initState();
    _items = Api.getWatchlist();
  }

  Future<void> _reload() async {
    setState(() => _items = Api.getWatchlist());
  }

  Future<void> _add() async {
    final v = _input.text.trim();
    if (v.isEmpty) return;
    try {
      await Api.addWatch(_kind, v);
      _input.clear();
      await _reload();
    } catch (e) {
      ScaffoldMessenger.of(context).showSnackBar(SnackBar(content: Text('$e')));
    }
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(title: const Text('Watchlist')),
      body: Column(
        children: [
          Padding(
            padding: const EdgeInsets.all(12),
            child: Row(
              children: [
                DropdownButton<String>(
                  value: _kind,
                  items: const [
                    DropdownMenuItem(value: 'ticker', child: Text('Ticker')),
                    DropdownMenuItem(value: 'keyword', child: Text('Keyword')),
                  ],
                  onChanged: (v) => setState(() => _kind = v ?? 'ticker'),
                ),
                const SizedBox(width: 8),
                Expanded(
                  child: TextField(
                    controller: _input,
                    decoration: InputDecoration(hintText: _kind == 'ticker' ? 'AAPL' : 'rate hike'),
                    onSubmitted: (_) => _add(),
                  ),
                ),
                IconButton(icon: const Icon(Icons.add), onPressed: _add),
              ],
            ),
          ),
          const Divider(height: 1),
          Expanded(
            child: FutureBuilder<List<dynamic>>(
              future: _items,
              builder: (ctx, snap) {
                if (!snap.hasData) return const Center(child: CircularProgressIndicator());
                final items = snap.data!;
                return ListView.builder(
                  itemCount: items.length,
                  itemBuilder: (_, i) {
                    final it = items[i] as Map<String, dynamic>;
                    return ListTile(
                      leading: Icon(it['kind'] == 'ticker' ? Icons.show_chart : Icons.search),
                      title: Text(it['value']),
                      subtitle: Text(it['kind']),
                      trailing: IconButton(
                        icon: const Icon(Icons.delete),
                        onPressed: () async {
                          await Api.deleteWatch(it['id'] as int);
                          await _reload();
                        },
                      ),
                    );
                  },
                );
              },
            ),
          ),
        ],
      ),
    );
  }
}

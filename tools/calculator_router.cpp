// Route single-driver redstone nets on a 3D track grid. A negotiated
// congestion pass resolves crossings that trap a greedy pad-to-pad router.
#include <algorithm>
#include <array>
#include <cstdlib>
#include <deque>
#include <iostream>
#include <queue>
#include <random>
#include <stdexcept>
#include <vector>

struct Pad { int owner = -1, mask = 0; }; // -1: free, -2: block, >=0: fixed pad
struct Edge { int net, from, to, rotation; };
struct Net { int id, root; std::vector<int> sinks, used; std::vector<Edge> edges; };
using Point = std::array<int, 3>;
constexpr int U = 4, D = 5, MOVES = 12, STATES = 13;
constexpr int cw[4] = {0, 2, 1, 3}; // east, south, west, north

int heading(int d) { return d < 4 ? d : (d < 8 ? U : D); }
int inverse(int d) { return d < 4 ? (d^1) : (d < 8 ? d+4 : d-4); }

// A spiral needs one clear side at each end. Pick its rotation per
// cable; no two passive lifts may touch without buffering between them.
bool compatible(int mask, int dir) {
    mask |= 1 << dir;
    unsigned lifts = unsigned(mask) >> 4;
    if (lifts == 0) return true;
    if ((lifts & (lifts-1)) != 0) return false;
    int lift = __builtin_ctz(lifts);
    int forbidden = cw[(lift + (lift >= 4 ? 1 : 0)) % 4];
    return !(mask & (1 << forbidden));
}

class Router {
    const int w, h, d, n;
    const std::vector<Pad> grid;
    std::vector<Point> coords;
    std::vector<std::array<int, 6>> neighbors;
    std::vector<int> cost, parent, stamp, closed, own, joint, usage, history;
    int query = 0, tree = 0, pressure = 0, pass = 0;
    Point lo, hi;

    int idx(int x, int y, int z) const { return (y*d+z)*w+x; }

    int estimate(int p) const {
        int total = 0;
        for (int i=0; i<3; ++i) {
            int a = coords[p][i];
            total += (i==1 ? 14 : 10)*std::max({0, a-hi[i], lo[i]-a});
        }
        return total;
    }

    bool linked(int p) const { return own[p] == tree; }
    int mask(int p) const { return grid[p].mask | (linked(p) ? joint[p] : 0); }

    void include(int p, Net& net) {
        own[p] = tree;
        joint[p] = 0;
        net.used.push_back(p);
        for (int i=0; i<3; ++i) {
            lo[i] = std::min(lo[i], coords[p][i]);
            hi[i] = std::max(hi[i], coords[p][i]);
        }
    }

    bool connect(Net& net, int target, int margin, bool exclusive) {
        ++query;
        Point lower, upper;
        for (int i=0; i<3; ++i) {
            lower[i] = std::min(lo[i], coords[target][i])-margin;
            upper[i] = std::max(hi[i], coords[target][i])+margin;
        }
        std::priority_queue<std::array<int, 3>> open;
        int start = target*STATES+MOVES;
        stamp[start] = query;
        cost[start] = 0;
        parent[start] = -1;
        open.push({-2*estimate(target), 0, start});
        int solved = -1;
        while (!open.empty()) {
            auto [priority, negative, cur] = open.top();
            open.pop();
            int p = cur/STATES, enter = cur%STATES;
            if (-negative != cost[cur] || closed[cur] == query) continue;
            closed[cur] = query;
            if (linked(p)) { solved = cur; break; }
            int current_mask = mask(p) | (enter == MOVES ? 0 : (1 << enter));
            for (int dir=0; dir<MOVES; ++dir) {
                int q = neighbors[p][heading(dir)];
                if (dir == enter || q == -1 || q == target || !compatible(current_mask, dir)) continue;
                if (grid[q].owner != -1 && !(grid[q].owner == net.id && linked(q))) continue;
                if (exclusive && usage[q] > 0) continue;
                const auto& at = coords[q];
                if (at[0]<lower[0] || at[0]>upper[0] || at[1]<lower[1] || at[1]>upper[1] || at[2]<lower[2] || at[2]>upper[2]) continue;
                int back = inverse(dir);
                if (!compatible(mask(q), back)) continue;
                int s = q*STATES+back;
                if (closed[s] == query) continue;
                int score = -negative + (dir<4 ? 10 : 14) + (enter != MOVES && dir != inverse(enter) ? 3 : 0);
                if (!linked(q)) score += pressure*usage[q] + history[q];
                if (stamp[s] == query && cost[s] <= score) continue;
                // Don't use a loop to re-enter a pad from another side.
                bool revisit = false;
                for (int r = parent[cur]; r != -1; r = parent[r]) {
                    if (r/STATES == q) { revisit = true; break; }
                }
                if (revisit) continue;
                stamp[s] = query;
                cost[s] = score;
                parent[s] = cur;
                open.push({-(score+2*estimate(q)), -score, s});
            }
        }
        if (solved == -1) return false;
        for (int from = solved; parent[from] != -1; from = parent[from]) {
            int to = parent[from], dir = from%STATES;
            if (linked(to/STATES)) throw std::runtime_error("Route self-intersection");
            include(to/STATES, net);
            joint[from/STATES] |= 1 << dir;
            joint[to/STATES] |= 1 << inverse(dir);
            net.edges.push_back({net.id, from/STATES, to/STATES, dir < 4 ? 0 : dir%4});
        }
        return true;
    }

    bool route(Net& net, bool exclusive=false) {
        for (int p : net.used) --usage[p];
        net.used.clear(); net.edges.clear();
        ++tree;
        lo = hi = coords[net.root];
        include(net.root, net);
        auto pending = net.sinks;
        while (!pending.empty()) {
            auto it = std::min_element(pending.begin(), pending.end(), [&](int a, int b){return estimate(a)<estimate(b);});
            // Later passes can detour around the congested port corridors.
            int margin = 8 + std::min(20, 2*pass);
            if (!connect(net, *it, margin, exclusive)
                && (exclusive || !connect(net, *it, std::max({w,h,d}), false))) {
                if (!exclusive) {
                    auto [x,y,z] = coords[*it];
                    std::cerr << "Unreachable pad " << x << ',' << y << ',' << z << " on net " << net.id << '\n';
                }
                net.used.clear(); net.edges.clear();
                return false;
            }
            pending.erase(it);
        }
        for (int p : net.used) ++usage[p];
        return true;
    }

    int congestion() const {
        int score = 0;
        for (int count : usage) score += std::max(0, count-1);
        return score;
    }

    bool uncross(std::vector<Net>& nets, std::mt19937& rng) {
        // Repair one pin neighborhood at a time. Keep the already-good
        // routes in place, and accept detours only if congestion drops.
        std::vector<int> bad, near(n, -1);
        int score = congestion(), stale = 0;
        for (int attempt=0; attempt<200 && score; ++attempt) {
            bad.clear();
            for (int p=0; p<n; ++p) if (usage[p]>1) bad.push_back(p);
            const int center = bad[attempt%bad.size()];
            const int radius = 1 + std::min(4, stale/16);
            history[center] += 40;
            std::deque<int> open{center};
            std::fill(near.begin(),near.end(),-1);
            near[center] = 0;
            while (!open.empty()) {
                int p=open.front(); open.pop_front();
                if (near[p]==radius) continue;
                for (int q : neighbors[p]) if (q>=0 && near[q]<0) {
                    near[q]=near[p]+1;
                    open.push_back(q);
                }
            }
            std::vector<int> group, order;
            std::vector<Net> before;
            for (int i=0;i<int(nets.size());++i) {
                auto& net=nets[i];
                if (std::any_of(net.used.begin(),net.used.end(),[&](int p){return near[p]>=0;})) {
                    group.push_back(i);
                    before.push_back(net);
                    for (int p: net.used) --usage[p];
                    net.used.clear();
                }
            }
            order=group;
            std::shuffle(order.begin(),order.end(),rng);
            if (attempt % 2 == 0) {
                // Start with the two conflicting cables, not a bystander.
                std::stable_partition(order.begin(),order.end(),[&](int i){
                    const auto& saved=before[std::lower_bound(group.begin(),group.end(),i)-group.begin()];
                    return std::find(saved.used.begin(),saved.used.end(),center)!=saved.used.end();
                });
            }
            bool routed=true;
            for (int i:order) if (!route(nets[i],true) && !route(nets[i])) { routed=false; break; }
            int next=congestion();
            if (routed && next<=score) {
                if (next<score) {
                    std::cerr << "Local repair " << attempt+1 << ": " << next << " shared pads\n";
                    stale=0;
                } else ++stale;
                score=next;
            } else {
                ++stale;
                for (size_t j=0;j<group.size();++j) {
                    auto& net=nets[group[j]];
                    for (int p:net.used) --usage[p];
                    net=std::move(before[j]);
                    for (int p:net.used) ++usage[p];
                }
            }
        }
        return score==0;
    }

    double weight(const Net& net) const {
        int max = 0;
        for (int p: net.sinks) {
            int dis = 0;
            for (int i=0; i<3; ++i) dis += std::abs(coords[net.root][i] - coords[p][i]);
            max = std::max(max, dis);
        }
        return max + 2.4*net.sinks.size();
    }

public:
    Router(int w_, int h_, int d_, const std::vector<Pad>& initial): w(w_), h(h_), d(d_), n(w*h*d),
        grid(initial), coords(n), neighbors(n), cost(n*STATES), parent(n*STATES), stamp(n*STATES), closed(n*STATES), own(n), joint(n), usage(n), history(n) {
        for (int y=0; y<h; ++y) for (int z=0; z<d; ++z) for (int x=0; x<w; ++x) {
            auto i = idx(x, y, z);
            coords[i] = {x, y, z};
            neighbors[i] = {x+1<w ? i+1 : -1, x>0 ? i-1 : -1,
                            z+1<d ? i+w : -1, z>0 ? i-w : -1,
                            y+1<h ? i+w*d : -1, y>0 ? i-w*d : -1};
        }
    }

    bool solve(std::vector<Net>& nets) {
        std::stable_sort(nets.begin(), nets.end(), [&](auto& a, auto& b){return weight(a)>weight(b);});
        std::mt19937 rng(5603);
        int shared = 0;
        bool repaired = false;
        for (int iter=0; iter<88; ++iter) {
            pass = iter;
            pressure = iter < 8 ? 65 + 25*iter : 900 + 39*iter;
            // Break pinches by reopening nearby routes as a group. A route
            // may need a free pad that a non-conflicting neighbor still owns.
            const bool reopen = !repaired && iter >= 11 && shared <= 10 && iter % 8 == 7;
            std::vector<int> area(n, -1);
            if (reopen) {
                std::deque<int> fringe;
                for (int p=0; p<n; ++p) if (usage[p]>1) {
                    area[p]=0;
                    fringe.push_back(p);
                }
                while (!fringe.empty()) {
                    int p=fringe.front(); fringe.pop_front();
                    if (area[p] == 1+(iter/24)%3) continue;
                    for (int q : neighbors[p]) if (q>=0 && area[q]<0) {
                        area[q]=area[p]+1;
                        fringe.push_back(q);
                    }
                }
            }
            std::vector<int> redo;
            for (size_t i=0; i<nets.size(); ++i)
                if (iter==0 || std::any_of(nets[i].used.begin(), nets[i].used.end(), [&](int p){return usage[p]>1 || area[p]>=0;}))
                    redo.push_back(int(i));
            if (reopen) for (int i : redo) {
                for (int p : nets[i].used) --usage[p];
                nets[i].used.clear();
            }
            if (iter % 3 == 1) std::reverse(redo.begin(), redo.end());
            if (reopen || iter % 3 == 2) std::shuffle(redo.begin(), redo.end(), rng);
            for (int i : redo)
                if (!route(nets[i])) return false;
            int conflicts = 0;
            for (int p=0; p<n; ++p) {
                if (usage[p] > 1) {
                    conflicts += usage[p]-1;
                    history[p] += 7*(usage[p]-1);
                }
            }
            if (conflicts == 0) return true;
            shared = conflicts;
            if (iter < 4 || iter % 4 == 3)
                std::cerr << "Routing pass " << iter+1 << ": " << conflicts << " shared pads to resolve\n";
            if (!repaired && iter>=12 && shared<=24) {
                repaired = true;
                if (uncross(nets,rng)) return true;
                shared = congestion();
            }
        }
        for (int p=0; p<n; ++p) if (usage[p]>1) {
            auto [x,y,z] = coords[p];
            std::cerr << "Still shared at " << x << ',' << y << ',' << z << ':';
            for (const auto& net : nets) if (std::find(net.used.begin(), net.used.end(), p)!=net.used.end()) std::cerr << ' ' << net.id;
            std::cerr << '\n';
        }
        return false;
    }
};

int main() {
    int w, h, d, pads, n;
    if (!(std::cin >> w >> h >> d >> pads >> n)) return 2;
    std::vector<Pad> initial(w*h*d);
    for (int j=0; j<pads; ++j) {
        int i;
        std::cin >> i;
        auto& pad = initial.at(i);
        std::cin >> pad.owner >> pad.mask;
    }
    std::vector<Net> nets(n);
    for (auto& net: nets) {
        int count;
        std::cin >> net.id >> net.root >> count;
        net.sinks.resize(count);
        for (auto& p: net.sinks) std::cin >> p;
    }
    Router router(w, h, d, initial);
    if (!router.solve(nets)) return 1;
    size_t count = 0;
    for (const auto& net : nets) count += net.edges.size();
    std::cerr << "Routed " << n << " nets using " << count << " edges\n";
    for (const auto& net : nets) for (auto e: net.edges)
        std::cout << e.net << ' ' << e.from << ' ' << e.to << ' ' << e.rotation << '\n';
}

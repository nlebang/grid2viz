import json
import time

from grid2kpi.episode.EpisodeAnalytics import EpisodeAnalytics
from grid2op.EpisodeData import EpisodeData
import os
import configparser
import csv
import pickle

from grid2op.PlotPlotly import PlotObs

graph = None


def make_network(episode):
    """
        Create a Plotly network graph with the layout configuration and the selected episode.

        :param episode: An episode containing targeted data for the graph.
        :return: Network graph
    """
    global graph
    if graph is None:
        graph = PlotObs(
            substation_layout=network_layout, observation_space=episode.observation_space)
    return graph


store = {}


def make_episode(agent, episode_name):
    """
        Load episode from cache. If not already in, compute episode data
        and save it in cache.

        :param agent: Agent Name
        :param episode_name: Name of the studied episode
        :return: Episode with computed data
    """
    if is_in_ram_cache(episode_name, agent):
        return get_from_ram_cache(episode_name, agent)
    elif is_in_fs_cache(episode_name, agent):
        episode = get_from_fs_cache(episode_name, agent)
        save_in_ram_cache(episode_name, agent, episode)
        return episode
    else:
        episode = compute_episode(episode_name, agent)
        save_in_fs_cache(episode_name, agent, episode)
        save_in_ram_cache(episode_name, agent, episode)
        return episode


def clear_fs_cache():
    os.rmdir(cache_dir)


def is_in_fs_cache(episode_name, agent):
    return os.path.isfile(get_fs_cached_file(episode_name, agent))


def get_fs_cached_file(episode_name, agent):
    episode_dir = os.path.join(cache_dir, episode_name)
    if not os.path.exists(episode_dir):
        os.makedirs(episode_dir)
    return os.path.join(episode_dir, agent + ".pickle")


def save_in_fs_cache(episode_name, agent, episode):
    path = get_fs_cached_file(episode_name, agent)
    with open(path, "wb") as f:
        pickle.dump(episode, f, protocol=4)


def get_from_fs_cache(episode_name, agent):
    beg = time.time()
    path = get_fs_cached_file(episode_name, agent)
    with open(path, "rb") as f:
        episode_loaded = pickle.load(f)
    end = time.time()
    print(f"end loading scenario file: {end - beg}")
    return episode_loaded


def compute_episode(episode_name, agent):
    path = os.path.join(base_dir, agent)
    return EpisodeAnalytics(EpisodeData.from_disk(
        path, episode_name
    ), episode_name, agent)


def is_in_ram_cache(episode_name, agent):
    return make_ram_cache_id(episode_name, agent) in store


def save_in_ram_cache(episode_name, agent, episode):
    store[make_ram_cache_id(episode_name, agent)] = episode


def get_from_ram_cache(episode_name, agent):
    return store[make_ram_cache_id(episode_name, agent)]


def make_ram_cache_id(episode_name, agent):
    return agent + episode_name


def check_all_tree_and_get_meta_and_best(base_dir, agents):
    best_agents = {}
    meta_json = {}

    for agent in agents:
        for scenario_name in os.listdir(os.path.join(base_dir, agent)):
            scenario_folder = os.path.join(base_dir, agent, scenario_name)
            if not os.path.isdir(scenario_folder):
                continue
            with open(os.path.join(scenario_folder, "episode_meta.json")) as f:
                episode_meta = json.load(fp=f)
                meta_json[scenario_name] = episode_meta
                if scenario_name not in best_agents:
                    best_agents[scenario_name] = {"value": -1, "agent": None, "out_of": 0}
                if best_agents[scenario_name]["value"] < episode_meta["nb_timestep_played"]:
                    best_agents[scenario_name]["value"] = episode_meta["nb_timestep_played"]
                    best_agents[scenario_name]["agent"] = agent
                    best_agents[scenario_name]['cum_reward'] = episode_meta['cumulative_reward']
            best_agents[scenario_name]["out_of"] = best_agents[scenario_name]["out_of"] + 1
    return meta_json, best_agents


"""
Initialisation routine
"""
''' Parsing of config file'''
path_cfg = os.path.join(
    os.path.abspath(os.path.dirname(__name__)),
    # os.path.pardir,
    # os.path.pardir,
    "config.ini"
)
parser = configparser.ConfigParser()
print("the config file used is located at: {}".format(path_cfg))
parser.read(path_cfg)
default_dir = os.environ.get("GRID2VIZ_ROOT")
if default_dir is None:
    default_dir = os.getcwd()

base_dir = parser.get("DEFAULT", "base_dir")
if base_dir == "":
    base_dir = os.path.join(default_dir, "data", "agents")

print("Agents ata used are located at: {}".format(base_dir))
cache_dir = os.path.join(base_dir, "_cache")
'''Parsing of agent folder tree'''
agents = sorted([file for file in os.listdir(base_dir)
                 if os.path.isdir(os.path.join(base_dir, file)) and not file.startswith("_")])
meta_json, best_agents = check_all_tree_and_get_meta_and_best(base_dir, agents)
scenarios = []
scenarios_agent = {}
agent_scenario = {}

for agent in agents:
    scen_path = os.path.join(base_dir, agent)
    scens = [file for file in os.listdir(
        scen_path) if os.path.isdir(os.path.join(scen_path, file))]
    scenarios_agent[agent] = scens
    for scen in scens:
        if scen not in agent_scenario:
            agent_scenario[scen] = []
        if agent not in agent_scenario[scen]:
            agent_scenario[scen].append(agent)
    scenarios = scenarios + scens

scenarios = set(scenarios)


'''Parsing of the environment configuration'''
env_conf_folder = parser.get('DEFAULT', 'env_conf_folder')
if env_conf_folder == "":
    env_conf_folder = os.path.join(default_dir, "data", "env_conf")
print("Data used are located at: {}".format(base_dir))
network_layout = []
try:
    network_layout_file = 'coords.csv'
    with open(os.path.join(env_conf_folder, network_layout_file)) as csv_file:
        csv_reader = csv.reader(csv_file, delimiter=';')
        line = 0  # skip the header part
        for coords in csv_reader:
            if line == 0:
                line = line + 1
                continue
            network_layout.append(
                (int(coords[0]),
                 int(coords[1]))
            )
except configparser.NoOptionError as ex:
    pass  # ignoring this error
except FileNotFoundError as e:
    pass  # ignoring that too
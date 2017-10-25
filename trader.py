import api_access_data
from coinbase.wallet.client import Client
from datetime import datetime, timedelta
import gdax
import numpy as np
import tensorflow as tf
import time
import trainer

gdax_client = gdax.PublicClient()
cb_client = Client(api_access_data.API_KEY, api_access_data.API_SECRET)

CURRENCY = 'ETH-USD'
SEQUENCE_LENGTH = 60
DATA_GRANULARITY = 60
HISTORICAL_DATA_BUFFER_SIZE = 10
SLEEP_TIME = 60
MODEL_DIR = 'model/'
MODEL_FILE_PATH = ''


def get_last_x_minute_data(x):
    end_time = datetime.now()
    start_time = end_time - timedelta(minutes=x + HISTORICAL_DATA_BUFFER_SIZE)
    new_data = gdax_client.get_product_historic_rates(CURRENCY,
                                                      start_time.isoformat(),
                                                      end_time.isoformat(),
                                                      DATA_GRANULARITY)
    new_data = np.array(new_data)[-x:, 4:6]

    return new_data


def get_last_minute_data():
    new_data = get_last_x_minute_data(2)

    return np.array(merge_candles(new_data))


def merge_candles(candles):
    volume = 0
    price = 0
    for candle in candles:
        volume += candle[1]
    for candle in candles:
        price += candle[0] * (candle[1] / volume)

    return [price, volume]


def get_initial_state():
    print("Collecting context for the last %d mins." % SEQUENCE_LENGTH)

    price_series = get_last_x_minute_data(SEQUENCE_LENGTH + 1)

    stationary_data = []
    for i in range(1, SEQUENCE_LENGTH + 1):
        datapoint = [(
            price_series[i][0] - price_series[i - 1][0]) / price_series[i
                                                                        - 1][0]
                     ]
        datapoint.append(price_series[i][1])
        stationary_data.append(datapoint)

    stationary_data = np.array(stationary_data)
    stationary_data = stationary_data.reshape(stationary_data.shape[0], 1,
                                              stationary_data.shape[1])

    return stationary_data, price_series[-1][0]


def trade(prediction):
    print(prediction)


def init():
    state, last_price = get_initial_state()

    # Restore trained model
    session = tf.Session()
    ckpt_file = ''
    if not MODEL_FILE_PATH:
        ckpt_file = tf.train.latest_checkpoint(MODEL_DIR)
    else:
        ckpt_file = MODEL_FILE_PATH
    meta_graph = tf.train.import_meta_graph(ckpt_file + '.meta')
    meta_graph.restore(session, ckpt_file)
    graph = tf.get_default_graph()
    inputs = graph.get_tensor_by_name(trainer.INPUT_PLACEHOLDER + ':0')
    pred = graph.get_tensor_by_name(trainer.OUTPUT_LAYER + ':0')

    while (True):
        prediction = session.run([pred], {inputs: state})

        prediction = np.squeeze(prediction)
        trade(prediction)

        time.sleep(SLEEP_TIME)

        # Get new data
        new_data = get_last_minute_data()
        new_price = new_data[1]
        new_data = new_data.reshape(1, 1, new_data.shape[0])
        np.append(state, new_data)
        state[-1, 0] = (state[-1, 0] - last_price) / last_price
        last_price = new_price


if __name__ == '__main__':
    init()

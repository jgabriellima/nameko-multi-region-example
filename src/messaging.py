from kombu import Exchange, Queue
from kombu.common import maybe_declare
from nameko.amqp import get_connection, get_producer
from nameko.constants import AMQP_URI_CONFIG_KEY, DEFAULT_SERIALIZER
from nameko.exceptions import serialize
from nameko.messaging import Consumer as NamekoConsumer

REGIONS = ['europe', 'asia', 'america']

ROUTING_KEY_ORDER_PRODUCT = 'order_product'
ROUTING_KEY_CALCULATE_TAXES = 'calculate_taxes'
ROUTING_KEY_CALCULATE_TAXES_REPLY = 'calculate_taxes_reply'

orders_exchange = Exchange(name='orders')

order_queue = Queue(
    exchange=orders_exchange,
    routing_key=ROUTING_KEY_ORDER_PRODUCT,
    name='fed.{}'.format(ROUTING_KEY_ORDER_PRODUCT)
)


class ReplyConsumer(NamekoConsumer):
    """Custom implementation of Nameko Consumer

    Consumes messages from queue in current region and sends a reply
    to a federated queue defined in `reply_to` message property.
    """

    def __init__(self, **kwargs):
        super(ReplyConsumer, self).__init__(None, kwargs)

    def handle_result(self, message, worker_ctx, result=None, exc_info=None):
        result, exc_info = self.send_response(message, result, exc_info)
        self.handle_message_processed(message, result, exc_info)
        return result, exc_info

    def setup(self):
        super(ReplyConsumer, self).setup()
        config = self.container.config

        """Declare consumer queue for this service in current region"""
        self.queue = Queue(
            exchange=orders_exchange,
            routing_key='{}_{}'.format(
                config['REGION'],
                ROUTING_KEY_CALCULATE_TAXES
            ),
            name='fed.{}_{}'.format(
                config['REGION'], ROUTING_KEY_CALCULATE_TAXES
            )
        )

        """Bind federated queues in all regions to
            `orders` exchange with correct routing key.
        """
        with get_connection(config[AMQP_URI_CONFIG_KEY]) as connection:

            maybe_declare(orders_exchange, connection)

            self._bind_queues_in_for_all_regions(
                ROUTING_KEY_CALCULATE_TAXES, connection
            )
            self._bind_queues_in_for_all_regions(
                ROUTING_KEY_CALCULATE_TAXES_REPLY, connection
            )

    def send_response(self, message, result, exc_info):

        config = self.container.config

        error = None
        if exc_info is not None:
            error = serialize(exc_info[1])

        with get_producer(config[AMQP_URI_CONFIG_KEY]) as producer:

            routing_key = message.properties.get('reply_to')

            msg = {'result': result, 'error': error}

            producer.publish(
                msg,
                exchange=orders_exchange,
                serializer=DEFAULT_SERIALIZER,
                routing_key=routing_key
            )

        return result, error

    def _bind_queues_in_for_all_regions(self, routing_key, connection):
        for region in REGIONS:
                maybe_declare(Queue(
                    exchange=orders_exchange,
                    routing_key='{}_{}'.format(
                        region, routing_key
                    ),
                    name='fed.{}_{}'.format(
                        region, routing_key
                    )
                ), connection)

consume_and_reply = ReplyConsumer.decorator


class DynamicConsumer(NamekoConsumer):
    """
    Alternative implementation of nameko.messaging.Consumer
    to allow for dynamic reply queue name declaration.
    """
    def __init__(self, **kwargs):
        super(DynamicConsumer, self).__init__(None, kwargs)

    def setup(self):
        reply_queue_name = "{}_{}".format(
            self.container.config['REGION'], ROUTING_KEY_CALCULATE_TAXES_REPLY
        )
        queue = Queue(
            exchange=orders_exchange,
            routing_key=reply_queue_name,
            name='fed.{}'.format(reply_queue_name)
        )
        self.queue = queue
        super(DynamicConsumer, self).setup()

consume_reply = DynamicConsumer.decorator

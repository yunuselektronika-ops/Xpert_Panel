import {
  Box,
  Button,
  Card,
  CardBody,
  CardHeader,
  Flex,
  FormControl,
  FormLabel,
  Heading,
  HStack,
  IconButton,
  Input,
  Modal,
  ModalBody,
  ModalCloseButton,
  ModalContent,
  ModalFooter,
  ModalHeader,
  ModalOverlay,
  Spinner,
  Stack,
  Stat,
  StatLabel,
  StatNumber,
  Switch,
  Table,
  Tbody,
  Td,
  Text,
  Th,
  Thead,
  Tr,
  useDisclosure,
  useToast,
  VStack,
  chakra,
} from "@chakra-ui/react";
import { Header } from "components/Header";
import { Footer } from "components/Footer";
import { FC, useEffect, useState } from "react";
import { TrashIcon, ArrowPathIcon } from "@heroicons/react/24/outline";
import { fetch } from "../service/http";
import { getAuthToken } from "../utils/authStorage";

const DeleteIcon = chakra(TrashIcon, { baseStyle: { w: 4, h: 4 } });
const RepeatIcon = chakra(ArrowPathIcon, { baseStyle: { w: 4, h: 4 } });

interface Source {
  id: number;
  name: string;
  url: string;
  enabled: boolean;
  priority: number;
  config_count: number;
  success_rate: number;
  last_fetched: string | null;
}

interface Stats {
  total_sources: number;
  enabled_sources: number;
  total_configs: number;
  active_configs: number;
  avg_ping: number;
  target_ips: string[];
  domain: string;
}

interface Config {
  id: number;
  protocol: string;
  server: string;
  port: number;
  remarks: string;
  ping_ms: number;
  packet_loss: number;
  is_active: boolean;
}

export const XpertPanel: FC = () => {
  const [sources, setSources] = useState<Source[]>([]);
  const [stats, setStats] = useState<Stats | null>(null);
  const [configs, setConfigs] = useState<Config[]>([]);
  const [loading, setLoading] = useState(false);
  const [updating, setUpdating] = useState(false);
  const { isOpen, onOpen, onClose } = useDisclosure();
  const [newSource, setNewSource] = useState({ name: "", url: "", priority: 1 });
  const toast = useToast();

  const fetchData = async () => {
    setLoading(true);
    try {
      const [sourcesRes, statsRes, configsRes] = await Promise.all([
        fetch("/api/xpert/sources", {
          headers: { Authorization: `Bearer ${getAuthToken()}` },
        }),
        fetch("/api/xpert/stats", {
          headers: { Authorization: `Bearer ${getAuthToken()}` },
        }),
        fetch("/api/xpert/configs", {
          headers: { Authorization: `Bearer ${getAuthToken()}` },
        }),
      ]);
      setSources(sourcesRes);
      setStats(statsRes);
      setConfigs(configsRes);
    } catch (error) {
      toast({
        title: "Error loading data",
        status: "error",
        duration: 3000,
      });
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchData();
  }, []);

  const handleAddSource = async () => {
    if (!newSource.name || !newSource.url) {
      toast({
        title: "Please fill all fields",
        status: "warning",
        duration: 3000,
      });
      return;
    }

    try {
      await fetch("/api/xpert/sources", {
        method: "POST",
        headers: {
          Authorization: `Bearer ${getAuthToken()}`,
          "Content-Type": "application/json",
        },
        body: JSON.stringify(newSource),
      });
      toast({
        title: "Source added",
        status: "success",
        duration: 3000,
      });
      setNewSource({ name: "", url: "", priority: 1 });
      onClose();
      fetchData();
    } catch (error) {
      toast({
        title: "Error adding source",
        status: "error",
        duration: 3000,
      });
    }
  };

  const handleDeleteSource = async (id: number) => {
    try {
      await fetch(`/api/xpert/sources/${id}`, {
        method: "DELETE",
        headers: { Authorization: `Bearer ${getAuthToken()}` },
      });
      toast({
        title: "Source deleted",
        status: "success",
        duration: 3000,
      });
      fetchData();
    } catch (error) {
      toast({
        title: "Error deleting source",
        status: "error",
        duration: 3000,
      });
    }
  };

  const handleToggleSource = async (id: number) => {
    try {
      await fetch(`/api/xpert/sources/${id}/toggle`, {
        method: "POST",
        headers: { Authorization: `Bearer ${getAuthToken()}` },
      });
      fetchData();
    } catch (error) {
      toast({
        title: "Error toggling source",
        status: "error",
        duration: 3000,
      });
    }
  };

  const handleUpdate = async () => {
    setUpdating(true);
    try {
      const result = await fetch("/api/xpert/update", {
        method: "POST",
        headers: { Authorization: `Bearer ${getAuthToken()}` },
      });
      toast({
        title: "Update complete",
        description: `${result.active_configs}/${result.total_configs} active configs`,
        status: "success",
        duration: 5000,
      });
      fetchData();
    } catch (error) {
      toast({
        title: "Error updating",
        status: "error",
        duration: 3000,
      });
    } finally {
      setUpdating(false);
    }
  };

  if (loading) {
    return (
      <VStack justifyContent="center" minH="100vh">
        <Spinner size="xl" />
      </VStack>
    );
  }

  return (
    <VStack justifyContent="space-between" minH="100vh" p="6" rowGap={4}>
      <Box w="full">
        <Header />

        {/* Statistics */}
        {stats && (
          <Card mt="4">
            <CardHeader>
              <Heading size="md">Xpert Panel Statistics</Heading>
            </CardHeader>
            <CardBody>
              <Flex gap={4} flexWrap="wrap">
                <Stat>
                  <StatLabel>Total Sources</StatLabel>
                  <StatNumber>{stats.total_sources}</StatNumber>
                </Stat>
                <Stat>
                  <StatLabel>Enabled Sources</StatLabel>
                  <StatNumber>{stats.enabled_sources}</StatNumber>
                </Stat>
                <Stat>
                  <StatLabel>Total Configs</StatLabel>
                  <StatNumber>{stats.total_configs}</StatNumber>
                </Stat>
                <Stat>
                  <StatLabel>Active Configs</StatLabel>
                  <StatNumber color="green.500">{stats.active_configs}</StatNumber>
                </Stat>
                <Stat>
                  <StatLabel>Avg Ping</StatLabel>
                  <StatNumber>{stats.avg_ping.toFixed(0)} ms</StatNumber>
                </Stat>
              </Flex>
              <Box mt={4}>
                <Text fontSize="sm" color="gray.500">
                  Target IPs: {stats.target_ips.join(", ")}
                </Text>
                <Text fontSize="sm" color="gray.500">
                  Domain: {stats.domain}
                </Text>
              </Box>
            </CardBody>
          </Card>
        )}

        {/* Sources */}
        <Card mt="4">
          <CardHeader>
            <Flex justify="space-between" align="center">
              <Heading size="md">Subscription Sources</Heading>
              <HStack>
                <Button
                  leftIcon={<RepeatIcon />}
                  colorScheme="blue"
                  onClick={handleUpdate}
                  isLoading={updating}
                >
                  Update Now
                </Button>
                <Button colorScheme="green" onClick={onOpen}>
                  Add Source
                </Button>
              </HStack>
            </Flex>
          </CardHeader>
          <CardBody>
            <Table variant="simple">
              <Thead>
                <Tr>
                  <Th>Name</Th>
                  <Th>URL</Th>
                  <Th>Configs</Th>
                  <Th>Success Rate</Th>
                  <Th>Last Fetched</Th>
                  <Th>Enabled</Th>
                  <Th>Actions</Th>
                </Tr>
              </Thead>
              <Tbody>
                {sources.map((source) => (
                  <Tr key={source.id}>
                    <Td>{source.name}</Td>
                    <Td fontSize="sm" maxW="300px" isTruncated>
                      {source.url}
                    </Td>
                    <Td>{source.config_count}</Td>
                    <Td>{source.success_rate.toFixed(1)}%</Td>
                    <Td fontSize="sm">
                      {source.last_fetched
                        ? new Date(source.last_fetched).toLocaleString()
                        : "Never"}
                    </Td>
                    <Td>
                      <Switch
                        isChecked={source.enabled}
                        onChange={() => handleToggleSource(source.id)}
                      />
                    </Td>
                    <Td>
                      <IconButton
                        aria-label="Delete"
                        icon={<DeleteIcon />}
                        colorScheme="red"
                        size="sm"
                        onClick={() => handleDeleteSource(source.id)}
                      />
                    </Td>
                  </Tr>
                ))}
              </Tbody>
            </Table>
          </CardBody>
        </Card>

        {/* Configs */}
        <Card mt="4">
          <CardHeader>
            <Heading size="md">Active Configurations ({configs.filter(c => c.is_active).length})</Heading>
          </CardHeader>
          <CardBody>
            <Table variant="simple" size="sm">
              <Thead>
                <Tr>
                  <Th>Protocol</Th>
                  <Th>Server</Th>
                  <Th>Port</Th>
                  <Th>Remarks</Th>
                  <Th>Ping</Th>
                  <Th>Loss</Th>
                  <Th>Status</Th>
                </Tr>
              </Thead>
              <Tbody>
                {configs
                  .filter((c) => c.is_active)
                  .slice(0, 20)
                  .map((config) => (
                    <Tr key={config.id}>
                      <Td>{config.protocol.toUpperCase()}</Td>
                      <Td fontSize="sm">{config.server}</Td>
                      <Td>{config.port}</Td>
                      <Td fontSize="sm">{config.remarks}</Td>
                      <Td>{config.ping_ms.toFixed(0)} ms</Td>
                      <Td>{config.packet_loss.toFixed(0)}%</Td>
                      <Td>
                        <Text color="green.500" fontWeight="bold">
                          Active
                        </Text>
                      </Td>
                    </Tr>
                  ))}
              </Tbody>
            </Table>
            {configs.filter((c) => c.is_active).length > 20 && (
              <Text mt={2} fontSize="sm" color="gray.500">
                Showing 20 of {configs.filter((c) => c.is_active).length} active configs
              </Text>
            )}
          </CardBody>
        </Card>
      </Box>

      <Footer />

      {/* Add Source Modal */}
      <Modal isOpen={isOpen} onClose={onClose}>
        <ModalOverlay />
        <ModalContent>
          <ModalHeader>Add Subscription Source</ModalHeader>
          <ModalCloseButton />
          <ModalBody>
            <Stack spacing={4}>
              <FormControl isRequired>
                <FormLabel>Name</FormLabel>
                <Input
                  value={newSource.name}
                  onChange={(e) =>
                    setNewSource({ ...newSource, name: e.target.value })
                  }
                  placeholder="My Subscription"
                />
              </FormControl>
              <FormControl isRequired>
                <FormLabel>URL</FormLabel>
                <Input
                  value={newSource.url}
                  onChange={(e) =>
                    setNewSource({ ...newSource, url: e.target.value })
                  }
                  placeholder="https://example.com/sub"
                />
              </FormControl>
              <FormControl>
                <FormLabel>Priority</FormLabel>
                <Input
                  type="number"
                  value={newSource.priority}
                  onChange={(e) =>
                    setNewSource({
                      ...newSource,
                      priority: parseInt(e.target.value),
                    })
                  }
                />
              </FormControl>
            </Stack>
          </ModalBody>
          <ModalFooter>
            <Button variant="ghost" mr={3} onClick={onClose}>
              Cancel
            </Button>
            <Button colorScheme="green" onClick={handleAddSource}>
              Add
            </Button>
          </ModalFooter>
        </ModalContent>
      </Modal>
    </VStack>
  );
};

export default XpertPanel;
